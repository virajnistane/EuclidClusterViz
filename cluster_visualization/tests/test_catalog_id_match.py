"""OBJECT_ID matching against CATRED tiles, the spec-z line on the p(z) plot, p(z) for a
clicked catalog marker, and the batch match script. CATRED tiles are small synthetic FITS."""

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import dash
import numpy as np
import pandas as pd
import plotly
from astropy.io import fits
from astropy.table import Table
from dash._callback_context import context_value
from dash._utils import AttributeDict

import cluster_visualization.callbacks.catalog_callbacks as cc
from cluster_visualization.callbacks.phz_callbacks import PHZCallbacks
from cluster_visualization.src.data import catalog_matcher as cm
from cluster_visualization.src.data.catalog_registry import CatalogRegistry
from cluster_visualization.src.data.catred_handler import CATREDHandler
from cluster_visualization.src.data.galaxy_catalog import CatalogSpec
from cluster_visualization.ui.layout import AppLayout

TILE_A, TILE_B = 102006993, 102006994


def _tile(directory, tile_id, object_ids, ra0):
    n = len(object_ids)
    pdf = np.tile(np.arange(10, dtype=np.float32), (n, 1)) + np.arange(n)[:, None]
    cols = [
        fits.Column("OBJECT_ID", "K", array=np.asarray(object_ids, dtype=np.int64)),
        fits.Column("RIGHT_ASCENSION", "D", array=ra0 + np.arange(n) * 1e-3),
        fits.Column("DECLINATION", "D", array=np.full(n, -66.0)),
        fits.Column("PHZ_PDF", "10E", array=pdf),
        fits.Column("PHZ_MODE_1", "E", array=np.full(n, 1.1, dtype=np.float32)),
        fits.Column("PHZ_MEDIAN", "E", array=np.linspace(1.0, 1.2, n).astype(np.float32)),
        fits.Column("PHZ_70_INT", "2E", array=np.tile([1.0, 1.3], (n, 1)).astype(np.float32)),
        fits.Column("FLUX_H_UNIF", "E", array=np.full(n, 5.0, dtype=np.float32)),
    ]
    path = os.path.join(directory, f"catred_{tile_id}.fits")
    fits.BinTableHDU.from_columns(cols).writeto(path)
    return path


def _catred_data(directory):
    """Two tiles: A holds IDs 1-3, B holds IDs 10-11."""
    info = pd.DataFrame(
        {
            "mertileid": [TILE_A, TILE_B],
            "dataset_release": ["DR1", "DR1"],
            "fits_file": [
                _tile(directory, TILE_A, [1, 2, 3], 55.0),
                _tile(directory, TILE_B, [10, 11], 56.0),
            ],
        }
    )
    return {"catred_info": info, "catred_dsr": "DR1"}


def _galaxies(ids, tiles=None, spec_z=None):
    n = len(ids)
    df = pd.DataFrame(
        {
            "RA": 55.0 + np.arange(n) * 1e-3,
            "DEC": np.full(n, -66.0),
            "OBJECT_ID": np.asarray(ids, dtype=np.int64),
        }
    )
    if tiles is not None:
        df["TILE_ID"] = np.asarray(tiles, dtype=np.int64)
    if spec_z is not None:
        df["SPEC_Z"] = spec_z
    return df


class LookupAndIdMatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = _catred_data(self.tmp.name)
        self.handler = CATREDHandler()

    def tearDown(self):
        self.tmp.cleanup()

    def test_lookup_by_object_id(self):
        found = self.handler.lookup_by_object_id([3, 1, 99, 10], self.data, [TILE_A, TILE_B])
        self.assertEqual(sorted(found["object_id"].tolist()), [1, 3, 10])  # 99 is in no tile
        i = found["object_id"].tolist().index(3)
        self.assertAlmostEqual(found["ra"][i], 55.002)
        self.assertEqual(found["phz_pdf"][i][0], 2.0)
        self.assertEqual(len(found["flux_h_unif"]), 3)
        with mock.patch(
            "cluster_visualization.src.data.catred_handler.fits.open", side_effect=AssertionError
        ):
            # Nothing to find: no tile is opened
            empty = self.handler.lookup_by_object_id([], self.data, [TILE_A])
        self.assertEqual(len(empty["object_id"]), 0)

    def test_match_by_id_uses_tile_then_searches_around(self):
        galaxies = _galaxies([2, 10, 99], tiles=[TILE_A, TILE_A, TILE_A], spec_z=[1.05, 1.5, 0.3])
        with mock.patch.object(
            self.handler, "_find_intersecting_tiles", return_value=[TILE_A, TILE_B]
        ) as around:
            result = cm.match_by_id(galaxies, self.handler, self.data)
        around.assert_called_once()  # 10 is not in its TILE_ID tile: searched around
        self.assertEqual(sorted(result.rows["OBJECT_ID"].tolist()), [2, 10])
        self.assertEqual(set(result.rows["MATCH_METHOD"]), {"object_id"})
        row = result.rows.set_index("OBJECT_ID").loc[2]
        # Galaxy 2 sits at RA 55.000, its CATRED source at 55.001 (Dec -66)
        self.assertAlmostEqual(row["SEP_ARCSEC"], 0.001 * 3600 * np.cos(np.radians(66.0)), places=3)
        self.assertAlmostEqual(row["PHZ_MEDIAN"], 1.1, places=5)
        # Each drawn source points back at its galaxy, for the spec-z on its p(z)
        n = len(result.display_matched_idx)
        z = cm.spec_z_values(galaxies, result.display_galaxy_idx, n)
        by_ra = dict(zip(result.catred_scatter["ra"], z["spec_z"]))
        self.assertAlmostEqual(by_ra[55.001], 1.05)
        self.assertAlmostEqual(by_ra[56.0], 1.5)

    def test_match_by_id_without_ids(self):
        no_ids = pd.DataFrame({"RA": [1.0], "DEC": [1.0]})
        self.assertIsNone(cm.match_by_id(no_ids, self.handler, self.data))
        with mock.patch.object(self.handler, "_find_intersecting_tiles", return_value=[]):
            result = cm.match_by_id(_galaxies([99]), self.handler, self.data)
        self.assertEqual(len(result.rows), 0)
        self.assertEqual(len(result.display_matched_idx), 0)

    def test_position_match_points_sources_at_nearest_galaxy(self):
        galaxies = pd.DataFrame({"RA": [10.0, 10.01], "DEC": [0.0, 0.0], "SPEC_Z": [0.3, 0.4]})
        scatter = {
            "ra": [10.0001, 10.0099],
            "dec": [0.0, 0.0],
            "phz_median": [0.3, 0.4],
            "phz_mode_1": [0.3, 0.4],
        }
        handler = SimpleNamespace(
            current_catred_data=None, update_catred_data_with_coverage=lambda *a: dict(scatter)
        )
        result = cm.match_by_position(galaxies, handler, {}, radius_arcsec=2.0)
        self.assertEqual(result.display_galaxy_idx.tolist(), [0, 1])

    def test_match_file_keeps_one_row_per_galaxy_and_cluster(self):
        rows = pd.DataFrame(
            {
                "CLUSTER_ID": [5, 7],
                "RA": [10.0, 10.0],
                "DEC": [0.0, 0.0],
                "CATRED_RA": [10.0, 10.0],
                "CATRED_DEC": [0.0, 0.0],
                "PHZ_MEDIAN": [0.3, 0.3],
                "PHZ_MODE": [0.3, 0.3],
                "SEP_ARCSEC": [0.1, 0.1],
                "MATCH_METHOD": ["position", "position"],
            }
        )
        spec = CatalogSpec("x", os.path.join(self.tmp.name, "ned.fits"), {"RA": "RA", "DEC": "DEC"})
        path = cm.write_matches(spec, rows)
        cm.write_matches(spec, rows.iloc[[0]].assign(PHZ_MEDIAN=0.9))
        table = Table.read(path).to_pandas().sort_values("CLUSTER_ID")
        self.assertEqual(
            table["CLUSTER_ID"].tolist(), [5, 7]
        )  # same galaxy, two clusters: two rows
        self.assertAlmostEqual(float(table["PHZ_MEDIAN"].iloc[0]), 0.9)


def _call(fn, prop_id, value, *args):
    token = context_value.set(
        AttributeDict(triggered_inputs=[{"prop_id": prop_id, "value": value}])
    )
    try:
        return fn(*args)
    finally:
        context_value.reset(token)


def _as_json(figure):
    return json.loads(json.dumps(figure, cls=plotly.utils.PlotlyJSONEncoder))


class AppIdMatchTest(unittest.TestCase):
    """Euclid-like catalog (OBJECT_ID, TILE_ID, SPEC_Z) through the app callbacks."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.data = _catred_data(d)
        rows = np.zeros(
            3,
            dtype=[
                ("object_id", ">i8"),
                ("right_ascension", ">f8"),
                ("declination", ">f8"),
                ("tile_index", ">i8"),
                ("z_spec_median_good", ">f4"),
                ("z_spec_sigma_good", ">f4"),
            ],
        )
        rows["object_id"] = [1, 2, 3]
        rows["right_ascension"] = 55.0 + np.arange(3) * 1e-3
        rows["declination"] = -66.0
        rows["tile_index"] = TILE_A
        rows["z_spec_median_good"] = [1.11, 1.12, 1.13]
        rows["z_spec_sigma_good"] = 0.01
        path = os.path.join(d, "euclid.fits")
        fits.BinTableHDU(rows).writeto(path)
        self.registry = CatalogRegistry(
            os.path.join(d, "catalogs.json"), cache_dir=os.path.join(d, "cache")
        )
        self.cid = self.registry.add(
            CatalogSpec(
                "Euclid spec-z",
                path,
                {
                    "RA": "right_ascension",
                    "DEC": "declination",
                    "OBJECT_ID": "object_id",
                    "TILE_ID": "tile_index",
                    "SPEC_Z": "z_spec_median_good",
                    "SPEC_Z_ERR": "z_spec_sigma_good",
                },
            )
        )
        self.handler = CATREDHandler()
        self.loader = SimpleNamespace(load_data=lambda algorithm: self.data)
        self.app = dash.Dash(__name__)
        self.app.layout = AppLayout.create_layout()
        cc.CatalogCallbacks(self.app, self.registry, self.handler, self.loader)
        PHZCallbacks(self.app, self.handler, self.loader, self.registry)
        self.fn = {}
        for value in self.app.callback_map.values():
            fn = value.get("callback")
            if fn is not None:
                fn = getattr(fn, "__wrapped__", fn)
                self.fn[fn.__name__] = fn
        self.ids = [{"type": "catalog-show", "index": self.cid}]
        figure = {
            "data": [],
            "layout": {"xaxis": {"range": [54.9, 55.1]}, "yaxis": {"range": [-66.1, -65.9]}},
        }
        prop = json.dumps({"index": self.cid, "type": "catalog-show"}, separators=(",", ":"))
        shown = _call(
            self.fn["show_catalogs"], prop + ".value", True, [True], self.ids, [""], figure, None
        )
        self.figure = _as_json(shown[0])

    def tearDown(self):
        self.tmp.cleanup()

    def test_marker_click_shows_pz_with_spec_z(self):
        self.assertEqual(self.figure["data"][0]["customdata"], [0, 1, 2])
        click = {"points": [{"curveNumber": 0, "pointNumber": 1, "customdata": 1}]}
        plot, tab, subtab = self.fn["update_phz_pdf_plot"](click, self.figure, "PZWAV")
        self.assertEqual((tab, subtab), ("phz-tab", "phz-catred-subtab"))
        self.assertIn("Euclid spec-z spec-z = 1.1200 ± 0.0100", [t.name for t in plot.data])
        self.assertEqual(len(plot.layout.shapes), 1)  # the ±err band
        self.assertEqual(list(plot.data[0].y), list(np.arange(10, dtype=float) + 1))  # OBJECT_ID 2

    def test_marker_click_without_object_id_explains(self):
        spec = self.registry.get(self.cid)
        spec.columns = {"RA": "right_ascension", "DEC": "declination"}
        self.registry.update(self.cid, spec)
        click = {"points": [{"curveNumber": 0, "pointNumber": 1, "customdata": 1}]}
        plot, tab, _ = self.fn["update_phz_pdf_plot"](click, self.figure, "PZWAV")
        self.assertEqual(tab, "phz-tab")
        self.assertIn("no OBJECT_ID mapped", plot.layout.annotations[0].text)

    def test_match_button_uses_object_id_and_click_shows_spec_z(self):
        with mock.patch.object(cc, "write_matches") as write:
            figure, feedback = self.fn["load_catred_near_catalogs"](
                1, 3.0, "PZWAV", True, 0.8, 24, None, self.figure, [True], self.ids
            )
        self.assertEqual(feedback, "Euclid spec-z: 3 of 3 galaxies found by OBJECT_ID")
        self.assertEqual(set(write.call_args.args[1]["MATCH_METHOD"]), {"object_id"})
        figure = _as_json(figure)
        match = figure["data"][1]
        self.assertIn("Euclid spec-z z_spec: 1.1100", match["text"][0])
        click = {
            "points": [{"curveNumber": 1, "pointNumber": 2, "x": match["x"][2], "y": match["y"][2]}]
        }
        plot, *_ = self.fn["update_phz_pdf_plot"](click, figure, "PZWAV")
        self.assertIn("Euclid spec-z spec-z = 1.1300 ± 0.0100", [t.name for t in plot.data])


class ScriptTest(unittest.TestCase):
    def setUp(self):
        scripts = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
        )
        sys.path.insert(0, scripts)
        import generate_catalog_catred_matches as script

        self.script = script

    def tearDown(self):
        sys.path.pop(0)

    def test_groups(self):
        df = pd.DataFrame({"RA": [10.2, 10.6, 50.0], "DEC": [0.0, 0.1, 0.0]})
        label, grouped = self.script.groups(df, 1.0)
        self.assertEqual((label, grouped.ngroups), ("sky cell", 2))
        self.assertEqual(self.script.groups(df.assign(CLUSTER_ID=[1, 1, 2]), 1.0)[0], "cluster")
        with_tiles = df.assign(TILE_ID=[1, 2, 3], CLUSTER_ID=1)
        self.assertEqual(self.script.groups(with_tiles, 1.0)[0], "MER tile")

    def test_find_catalog_by_name_or_id(self):
        with tempfile.TemporaryDirectory() as d:
            registry = CatalogRegistry(os.path.join(d, "c.json"))
            cid = registry.add(CatalogSpec("NED spec-z", "/x.fits", {"RA": "RA", "DEC": "DEC"}))
            self.assertEqual(self.script.find_catalog(registry, "ned SPEC-z").id, cid)
            self.assertEqual(self.script.find_catalog(registry, cid).id, cid)
            self.assertIsNone(self.script.find_catalog(registry, "other"))


if __name__ == "__main__":
    unittest.main()
