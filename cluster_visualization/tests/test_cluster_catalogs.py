"""External cluster catalogs: roles per catalog kind, mapping suggestions and checks,
loading, and the cross-match with the Euclid merged clusters."""

import json
import os
import tempfile
import unittest
from types import SimpleNamespace

import dash
import numpy as np
import pandas as pd
from astropy.io import fits

import cluster_visualization.callbacks.catalog_callbacks as cc
import cluster_visualization.tests.test_catalog_callbacks as tcc
from cluster_visualization.callbacks.phz_callbacks import PHZCallbacks
from cluster_visualization.src.data import cluster_matcher as cm
from cluster_visualization.src.data.catalog_registry import CatalogRegistry
from cluster_visualization.src.data.galaxy_catalog import (
    CLUSTER,
    GALAXY,
    CatalogSpec,
    GalaxyCatalog,
    column_units,
    find_table,
    inspect_columns,
    roles_for,
    suggest_mapping,
    validate_mapping,
)
from cluster_visualization.src.visualization import catalog_traces as ct
from cluster_visualization.src.visualization.trace_registry import TraceRegistry, TraceType
from cluster_visualization.src.visualization.traces import TraceCreator

REAL_SPT = os.path.join(os.path.dirname(__file__), "..", "..", "extra_files", "SPT3G_EDFS.fit")
SPT_MAPPING = {
    "RA": "RAJ2000",
    "DEC": "DEJ2000",
    "SOURCE_ID": "IAUName",
    "Z": "z",
    "Z_ERR": "e_z",
    "MASS": "M500c",
    "RICHNESS": "lambda",
    "SNR": "xi",
}


def _spt_fits(directory, n=5):
    """SPT-3G EDFS layout (VizieR J/A+A/706/A17): IAU names, xi, z with gaps, M500c in 1e14 Msun."""
    cols = [
        fits.Column("IAUName", "17A", array=[f"SPT-CL J033{i}-5046" for i in range(n)]),
        fits.Column("RAJ2000", "D", unit="deg", array=np.linspace(54.0, 55.0, n)),
        fits.Column("DEJ2000", "D", unit="deg", array=np.linspace(-51.0, -50.0, n)),
        fits.Column("xi", "D", array=np.linspace(4.5, 20.0, n)),
        fits.Column("thetacore", "E", array=np.full(n, 0.5)),
        fits.Column("z", "D", array=[0.75, np.nan, 0.3, 1.1, 0.5][:n]),
        fits.Column("e_z", "D", array=[0.02, np.nan, 0.01, 0.05, 0.02][:n]),
        fits.Column("M500c", "D", unit="1e+14solMass", array=[3.7, np.nan, 2.0, 4.1, 5.0][:n]),
        fits.Column("lambda", "D", array=[189.0, np.nan, 40.0, 60.0, 80.0][:n]),
        fits.Column("zucont", "D", array=[np.nan, 0.96, -99.9, np.nan, np.nan][:n]),
        fits.Column("LOS", "I", array=np.zeros(n, dtype=np.int16)),
    ]
    path = os.path.join(directory, "spt.fit")
    fits.HDUList([fits.PrimaryHDU(), fits.BinTableHDU.from_columns(cols)]).writeto(path)
    return path


def _merged(ra, dec, z, ids=None):
    """Euclid merged-catalog rows with the columns the cross-match reads."""
    rows = np.zeros(
        len(ra),
        dtype=[
            ("ID_UNIQUE_CLUSTER", "i8"),
            ("RIGHT_ASCENSION_CLUSTER", "f8"),
            ("DECLINATION_CLUSTER", "f8"),
            ("Z_CLUSTER", "f8"),
        ],
    )
    rows["ID_UNIQUE_CLUSTER"] = ids if ids is not None else 1000 + np.arange(len(ra))
    rows["RIGHT_ASCENSION_CLUSTER"] = ra
    rows["DECLINATION_CLUSTER"] = dec
    rows["Z_CLUSTER"] = z
    return rows


def _data_near(df, algorithm="PZWAV"):
    """Euclid clusters 0.5' north of SPT rows 0 (z 0.75; Euclid z 0.76) and 1 (no z), two
    near row 0 (the second 1.5' away), and one far away."""
    offset = 0.5 / 60.0
    return {
        "algorithm": algorithm,
        "data_detcluster_mergedcat": _merged(
            ra=[df["RA"][0], df["RA"][1], df["RA"][0], 100.0],
            dec=[df["DEC"][0] + offset, df["DEC"][1] + offset, df["DEC"][0] + 3 * offset, 0.0],
            z=[0.76, 0.4, 0.74, 0.5],
            ids=[11, 22, 44, 33],
        ),
    }


class TestClusterRoles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = _spt_fits(self.tmp.name)
        self.table = find_table(inspect_columns(self.path), None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_roles_per_kind(self):
        galaxy = {r.name for r in roles_for(GALAXY)}
        cluster = {r.name for r in roles_for(CLUSTER)}
        self.assertEqual(galaxy & cluster, {"RA", "DEC", "SOURCE_ID"})
        self.assertIn("SPEC_Z", galaxy)
        self.assertNotIn("SPEC_Z", cluster)
        self.assertTrue({"Z", "Z_ERR", "MASS", "RICHNESS", "SNR"} <= cluster)

    def test_spt_layout_prefills_as_clusters(self):
        self.assertEqual(suggest_mapping(self.table, CLUSTER), SPT_MAPPING)
        # As galaxies the same file maps z to spec-z, as before
        galaxy = suggest_mapping(self.table)
        self.assertEqual(galaxy.get("SPEC_Z"), "z")
        self.assertNotIn("MASS", galaxy)

    def test_units_from_the_file(self):
        self.assertEqual(
            column_units(self.table, SPT_MAPPING),
            {"RA": "deg", "DEC": "deg", "MASS": "1e+14solMass"},
        )

    @unittest.skipUnless(os.path.isfile(REAL_SPT), "extra_files/SPT3G_EDFS.fit not present")
    def test_real_spt3g_file(self):
        table = find_table(inspect_columns(REAL_SPT), None)
        self.assertEqual(table.nrows, 217)
        self.assertEqual(suggest_mapping(table, CLUSTER), SPT_MAPPING)
        spec = CatalogSpec("SPT-3G EDFS", REAL_SPT, SPT_MAPPING, hdu=table.hdu, kind=CLUSTER)
        self.assertTrue(validate_mapping(spec, table).ok)

    def test_validate_cluster_settings_and_roles(self):
        spec = CatalogSpec("SPT", self.path, dict(SPT_MAPPING), kind=CLUSTER)
        result = validate_mapping(spec, self.table)
        self.assertTrue(result.ok, result.errors)

        bad = CatalogSpec(
            "SPT", self.path, dict(SPT_MAPPING), kind=CLUSTER, match_radius_arcmin=0, match_dz=-1
        )
        errors = " ".join(validate_mapping(bad, self.table).errors)
        self.assertIn("Match radius", errors)
        self.assertIn("Δz", errors)

        # A galaxy-only role on a cluster catalog is refused
        wrong = CatalogSpec("SPT", self.path, {**SPT_MAPPING, "SPEC_Z": "z"}, kind=CLUSTER)
        self.assertIn("SPEC_Z", " ".join(validate_mapping(wrong, self.table).errors))

    def test_sentinel_warning_and_missing_on_load(self):
        mapping = {**SPT_MAPPING, "Z": "zucont"}
        spec = CatalogSpec("SPT", self.path, mapping, kind=CLUSTER)
        result = validate_mapping(spec, self.table)
        self.assertTrue(result.ok)
        self.assertTrue(any("-99" in w for w in result.warnings), result.warnings)

        catalog = GalaxyCatalog(spec, cache_dir=self.tmp.name)
        self.assertTrue(catalog.load())
        z = catalog.df["Z"].to_numpy()
        self.assertTrue(np.isnan(z[2]))  # -99.9 read as missing
        self.assertAlmostEqual(z[1], 0.96)

    def test_load_describe_and_capabilities(self):
        spec = CatalogSpec("SPT", self.path, dict(SPT_MAPPING), kind=CLUSTER)
        catalog = GalaxyCatalog(spec, cache_dir=self.tmp.name)
        self.assertTrue(catalog.load())
        self.assertEqual(list(catalog.df["SOURCE_ID"])[0], "SPT-CL J0330-5046")
        self.assertEqual(catalog.status, "5 clusters (4 with z)")
        self.assertEqual(catalog.capabilities(), {"display", "cluster_match", "cluster_filter"})

    def test_spec_round_trip_and_old_files(self):
        spec = CatalogSpec(
            "SPT",
            self.path,
            dict(SPT_MAPPING),
            kind=CLUSTER,
            match_radius_arcmin=1.5,
            units={"MASS": "1e+14solMass"},
        )
        self.assertEqual(CatalogSpec.from_dict(json.loads(json.dumps(spec.to_dict()))), spec)
        # A spec written before catalog kinds is a galaxy catalog; unknown roles are dropped
        old = CatalogSpec.from_dict(
            {"name": "NED", "path": "/x.fits", "columns": {"RA": "RA", "DEC": "DEC", "Z": "Z"}}
        )
        self.assertEqual(old.kind, GALAXY)
        self.assertEqual(old.columns, {"RA": "RA", "DEC": "DEC"})

    def test_registry_keeps_kind(self):
        registry = CatalogRegistry(os.path.join(self.tmp.name, "catalogs.json"))
        cid = registry.add(CatalogSpec("SPT", self.path, dict(SPT_MAPPING), kind=CLUSTER))
        again = CatalogRegistry(registry.path)
        self.assertEqual(again.get(cid).kind, CLUSTER)
        self.assertEqual([s.id for s in again.with_capability("cluster_filter")], [cid])
        self.assertEqual(again.with_capability("match_position"), [])


class TestMatchClusters(unittest.TestCase):
    def _ext(self, ra, dec, z=None):
        df = pd.DataFrame({"RA": np.asarray(ra, float), "DEC": np.asarray(dec, float)})
        if z is not None:
            df["Z"] = np.asarray(z, float)
        return df

    def test_radius_edge_and_redshift_cut(self):
        arcmin = 1 / 60.0
        merged = _merged(
            ra=[10.0, 10.0, 10.0, 20.0],
            dec=[1.95 * arcmin, 2.05 * arcmin, 0.5 * arcmin, 0.0],
            z=[0.5, 0.5, 0.9, 0.5],
        )
        ext = self._ext([10.0], [0.0], [0.5])
        pairs = cm.match_clusters(ext, merged, radius_arcmin=2.0, dz=0.05)
        # Inside the radius: row 0; just outside: row 1; inside but Δz too large: row 2
        self.assertEqual(list(pairs["EUCLID_ROW"]), [0])
        self.assertAlmostEqual(pairs["SEP_ARCMIN"].iloc[0], 1.95, places=4)
        self.assertAlmostEqual(pairs["DZ"].iloc[0], 0.0)
        self.assertTrue(pairs["BEST"].iloc[0])

    def test_position_only_without_redshift_and_best_is_nearest(self):
        arcmin = 1 / 60.0
        merged = _merged(ra=[10.0, 10.0], dec=[1.5 * arcmin, 0.5 * arcmin], z=[0.2, np.nan])
        pairs = cm.match_clusters(self._ext([10.0], [0.0], [np.nan]), merged, 2.0, 0.05)
        self.assertEqual(list(pairs["EUCLID_ROW"]), [1, 0])
        self.assertEqual(list(pairs["BEST"]), [True, False])
        self.assertTrue(pairs["DZ"].isna().all())
        # No Z column at all: by position only as well
        self.assertEqual(len(cm.match_clusters(self._ext([10.0], [0.0]), merged, 2.0, 0.05)), 2)

    def test_across_ra_zero(self):
        arcmin = 1 / 60.0
        merged = _merged(ra=[359.99], dec=[0.0], z=[0.4])
        pairs = cm.match_clusters(self._ext([0.005], [0.0], [0.41]), merged, 2.0, 0.05)
        self.assertEqual(len(pairs), 1)
        self.assertAlmostEqual(pairs["SEP_ARCMIN"].iloc[0], 0.015 * 60, places=3)
        self.assertLess(pairs["SEP_ARCMIN"].iloc[0], 2.0 + arcmin)

    def test_ext_row_labels_and_empty_inputs(self):
        merged = _merged(ra=[10.0], dec=[0.0], z=[0.5])
        ext = self._ext([30.0, 10.0], [0.0, 0.0], [0.5, 0.5])
        ext.index = [7, 9]
        pairs = cm.match_clusters(ext, merged, 1.0, 0.05)
        self.assertEqual(list(pairs["EXT_ROW"]), [9])
        self.assertEqual(list(pairs["ID_UNIQUE_CLUSTER"]), [1000])
        self.assertEqual(len(cm.match_clusters(ext.iloc[0:0], merged, 1.0, 0.05)), 0)
        self.assertEqual(len(cm.match_clusters(ext, merged[0:0], 1.0, 0.05)), 0)
        self.assertEqual(
            list(cm.match_clusters(ext, merged[0:0], 1.0, 0.05).columns), list(cm.MATCH_COLUMNS)
        )


class TestCachedMatchesAndCounterparts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = _spt_fits(self.tmp.name)
        spec = CatalogSpec("SPT", path, dict(SPT_MAPPING), kind=CLUSTER)
        self.catalog = GalaxyCatalog(spec, cache_dir=self.tmp.name)
        self.catalog.load()
        df = self.catalog.df
        # Euclid clusters 0.5' from SPT rows 0 (z 0.75) and 1 (no z), and one far away
        offset = 0.5 / 60.0
        self.data = {
            "algorithm": "PZWAV",
            "data_detcluster_mergedcat": _merged(
                ra=[df["RA"][0], df["RA"][1], 100.0],
                dec=[df["DEC"][0] + offset, df["DEC"][1] + offset, 0.0],
                z=[0.76, 0.4, 0.5],
                ids=[11, 22, 33],
            ),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_cached_per_algorithm_and_setting(self):
        first = cm.cached_matches(self.catalog, self.data)
        self.assertIs(cm.cached_matches(self.catalog, self.data), first)
        self.assertEqual(sorted(cm.matched_cluster_ids(self.catalog, self.data)), [11, 22])

        other = dict(self.data, algorithm="AMICO")
        self.assertIsNot(cm.cached_matches(self.catalog, other), first)
        self.catalog.spec.match_radius_arcmin = 0.1
        self.assertEqual(len(cm.cached_matches(self.catalog, self.data)), 0)
        self.assertLessEqual(len(self.catalog.match_cache), cm.CACHE_SIZE)

        summary = cm.match_summary(first, len(self.catalog.df))
        self.assertEqual(summary, {"external": 5, "matched": 2, "position_only": 1, "euclid": 2})

    def test_counterparts_of_one_euclid_cluster(self):
        merged = self.data["data_detcluster_mergedcat"]
        near = cm.counterparts(
            self.catalog,
            merged["RIGHT_ASCENSION_CLUSTER"][0],
            merged["DECLINATION_CLUSTER"][0],
            0.76,
        )
        self.assertEqual(list(near["SOURCE_ID"]), ["SPT-CL J0330-5046"])
        self.assertAlmostEqual(near["SEP_ARCMIN"].iloc[0], 0.5, places=3)
        # Too far in redshift: no counterpart
        self.assertEqual(
            len(
                cm.counterparts(
                    self.catalog,
                    merged["RIGHT_ASCENSION_CLUSTER"][0],
                    merged["DECLINATION_CLUSTER"][0],
                    1.5,
                )
            ),
            0,
        )
        self.assertEqual(len(cm.counterparts(self.catalog, 100.0, 0.0, 0.5)), 0)


class ClusterCatalogCallbackTest(unittest.TestCase):
    """The External catalogs section with a cluster catalog, callbacks called directly."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.spt = _spt_fits(self.tmp.name)
        self.registry = CatalogRegistry(
            os.path.join(self.tmp.name, "catalogs.json"),
            cache_dir=os.path.join(self.tmp.name, "cache"),
        )
        self.catred = SimpleNamespace(current_catred_data={})
        self.app = dash.Dash(__name__)
        self.app.layout = tcc.AppLayout.create_layout()
        cc.CatalogCallbacks(self.app, self.registry, self.catred, SimpleNamespace())
        self.fn = {}
        for value in self.app.callback_map.values():
            fn = value.get("callback")
            if fn is not None:
                fn = getattr(fn, "__wrapped__", fn)
                self.fn[fn.__name__] = fn

    def tearDown(self):
        self.tmp.cleanup()

    def _read(self):
        return tcc._call(
            self.fn["read_catalog_columns"],
            "catalog-read-button.n_clicks",
            1,
            1,
            None,
            {"mode": "add"},
            self.spt,
        )[0]

    def _fill(self, trigger, store, kind, state=None):
        out = tcc._call(
            self.fn["fill_catalog_mapping"], trigger, kind, store, 0, kind, state or {"mode": "add"}
        )
        n = len(cc.ROLES)
        values = dict(zip([r.name for r in cc.ROLES], out[1 : 2 * n : 2]))
        styles = dict(zip([r.name for r in cc.ROLES], out[2 * n : 3 * n]))
        return out, values, styles, out[3 * n : 3 * n + 3]

    def test_kind_switch_shows_the_kinds_rows(self):
        _, _, styles, (match_style, radius, dz) = self._fill(
            "catalog-kind-radio.value", None, CLUSTER
        )
        self.assertEqual(styles["SPEC_Z"], cc.HIDDEN)
        self.assertIsNone(styles["Z"])
        self.assertIsNone(styles["RA"])
        self.assertEqual(match_style, cc.SHOWN)
        self.assertIs(radius, dash.no_update)
        _, _, styles, (match_style, _, _) = self._fill("catalog-kind-radio.value", None, GALAXY)
        self.assertEqual((styles["Z"], styles["SPEC_Z"], match_style), (cc.HIDDEN, None, cc.HIDDEN))

    def test_fill_suggests_cluster_roles(self):
        store = self._read()
        _, values, _, (_, radius, dz) = self._fill("catalog-table-store.data", store, CLUSTER)
        self.assertEqual({k: v for k, v in values.items() if v}, SPT_MAPPING)
        self.assertEqual((radius, dz), (2.0, 0.05))
        # The same file as galaxies: z is a spec-z, no cluster roles
        _, values, _, _ = self._fill("catalog-kind-radio.value", store, GALAXY)
        self.assertEqual((values["SPEC_Z"], values["Z"]), ("z", None))

    def _save(self, roles, kind=CLUSTER, radius=1.5, dz=0.1):
        values = [roles.get(r.name) for r in cc.ROLES]
        args = [0, 1, self._read(), 0, *values, None, [], "SPT-3G", "#00aa00", "star", 10]
        args += [{"mode": "add"}, 3, None, None, kind, radius, dz]
        return tcc._call(self.fn["check_or_save_catalog"], "catalog-save-button.n_clicks", 1, *args)

    def test_save_keeps_only_the_kinds_roles(self):
        # A galaxy role left from switching kind is dropped
        feedback, is_open, *_ = self._save({**SPT_MAPPING, "SPEC_Z": "z"})
        self.assertFalse(is_open, feedback)
        (spec,) = self.registry.list()
        self.assertEqual(
            (spec.kind, spec.columns, spec.match_radius_arcmin, spec.match_dz),
            (CLUSTER, SPT_MAPPING, 1.5, 0.1),
        )
        self.assertEqual(spec.units, {"RA": "deg", "DEC": "deg", "MASS": "1e+14solMass"})

    def test_save_refuses_a_missing_radius(self):
        feedback, is_open, *_ = self._save(SPT_MAPPING, radius=None)
        self.assertIs(is_open, dash.no_update)
        self.assertIn("Match radius", str(feedback))
        self.assertEqual(self.registry.list(), [])

    def test_marker_hover_badges_and_clicks(self):
        cid = self.registry.add(
            CatalogSpec(
                "SPT-3G", self.spt, dict(SPT_MAPPING), kind=CLUSTER, units={"MASS": "1e+14solMass"}
            )
        )
        rows = self.fn["render_catalog_list"](1, [False], [{"type": "catalog-show", "index": cid}])
        self.assertIn("cluster catalog", str(rows[0]))

        ids = [{"type": "catalog-show", "index": cid}]
        figure, statuses = tcc._call(
            self.fn["show_catalogs"],
            tcc._pid("catalog-show", cid, "value"),
            True,
            [True],
            ids,
            [""],
            tcc._cluster_figure(),
            None,
            None,
        )
        self.assertEqual(statuses, ["5 clusters (4 with z)"])
        trace = tcc._as_json(figure)["data"][0]
        self.assertEqual(
            (trace["meta"]["kind"], trace["meta"]["catalog_kind"]), ("catalog", CLUSTER)
        )
        self.assertIn("Mass [1e+14solMass]: 3.7000", trace["text"][0])
        self.assertIn("SNR: 4.5000", trace["text"][0])
        self.assertIn("<b>SPT-3G</b>", trace["text"][0])
        # A cluster with missing values lists them as nan instead of leaving them out
        for line in ("z: nan", "z err: nan", "Mass [1e+14solMass]: nan", "Richness: nan"):
            self.assertIn(line, trace["text"][1])
        self.assertIn("SNR: 8.3750", trace["text"][1])

        # No p(z) for a cluster marker
        app = dash.Dash(__name__)
        PHZCallbacks(app, catred_handler=self.catred, catalog_registry=self.registry)
        update = next(
            v["callback"] for k, v in app.callback_map.items() if "phz-pdf-plot.figure" in k
        )
        update = getattr(update, "__wrapped__", update)
        click = {"points": [{"curveNumber": 0, "pointNumber": 0, "customdata": 0, "x": 54.0}]}
        self.assertEqual(update(click, tcc._as_json(figure)), (dash.no_update,) * 3)

        # CATRED near shown catalogs: only galaxy catalogs take part
        out = self.fn["load_catred_near_catalogs"](
            1, 3.0, "PZWAV", True, 0.8, 24, None, figure, [True], ids
        )
        self.assertEqual(out[1], "Show a galaxy catalog first.")


class HoverMissingValuesTest(unittest.TestCase):
    def test_cluster_catalogs_show_nan_galaxy_catalogs_skip(self):
        df = pd.DataFrame(
            {"RA": [10.0], "DEC": [-5.0], "SOURCE_ID": [None], "Z": [np.nan], "SPEC_Z": [np.nan]}
        )
        cluster = CatalogSpec("SPT", "x.fits", {"RA": "a", "DEC": "b", "Z": "z"}, kind=CLUSTER)
        text = ct.hover_texts(cluster, df[["RA", "DEC", "SOURCE_ID", "Z"]])[0]
        self.assertIn("ID: nan", text)
        self.assertIn("z: nan", text)
        galaxy = CatalogSpec("NED", "x.fits", {"RA": "a", "DEC": "b", "SPEC_Z": "z"})
        text = ct.hover_texts(galaxy, df[["RA", "DEC", "SOURCE_ID", "SPEC_Z"]])[0]
        self.assertNotIn("nan", text)
        self.assertNotIn("z_spec", text)


class ClusterMatchTraceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.spt = _spt_fits(self.tmp.name)
        self.registry = CatalogRegistry(
            os.path.join(self.tmp.name, "catalogs.json"),
            cache_dir=os.path.join(self.tmp.name, "cache"),
        )
        self.cid = self.registry.add(
            CatalogSpec("SPT-3G", self.spt, dict(SPT_MAPPING), kind=CLUSTER, color="#123456")
        )
        self.catalog = self.registry.catalog(self.cid)
        self.catalog.load()
        self.data = _data_near(self.catalog.df)

    def tearDown(self):
        self.tmp.cleanup()

    def test_links_and_rings(self):
        traces, note = ct.cluster_match_traces(self.catalog, self.data)
        self.assertEqual(
            note, "SPT-3G: 2 of 5 matched (PZWAV, 2′, Δz/(1+z) ≤ 0.05; 1 by position only)"
        )
        links, rings = traces
        self.assertEqual(
            [TraceRegistry.classify_trace(t) for t in traces], [TraceType.CATALOG_MATCH] * 2
        )
        self.assertEqual(rings.name, "Catalog match: SPT-3G ↔ Euclid PZWAV")
        self.assertEqual((links.legendgroup, links.showlegend), (rings.name, False))
        self.assertTrue(links.meta["links"])
        self.assertEqual(rings.meta["algorithm"], "PZWAV")
        # Three pairs (two for row 0), one segment each: start, end, gap
        self.assertEqual(len(links.x), 9)
        self.assertTrue(np.isnan(links.x[2]))
        self.assertEqual(len(rings.x), 2)
        self.assertIn("SPT-CL J0330-5046", rings.text[0])
        self.assertIn("Euclid ID 11: 0.50′, Δz/(1+z) 0.006", rings.text[0])
        self.assertIn("+1 more Euclid cluster(s) within 2′", rings.text[0])
        self.assertIn("Euclid ID 22: 0.50′, by position (no z)", rings.text[1])
        self.assertIn("z nan, Euclid z 0.400", rings.text[1])  # missing redshift shown

    def test_rebuilt_traces_keep_their_style(self):
        traces, _ = ct.cluster_match_traces(self.catalog, self.data)
        figure = tcc._as_json({"data": traces, "layout": {}})
        rebuilt = TraceRegistry.extract_traces(figure, {TraceType.CATALOG_MATCH})[
            TraceType.CATALOG_MATCH
        ]
        self.assertEqual(rebuilt[0].line.color, "#123456")
        self.assertEqual(rebuilt[0].legendgroup, rebuilt[1].name)

    def test_render_rebuilds_for_another_algorithm(self):
        creator = TraceCreator(catalog_registry=self.registry)
        traces, _ = ct.cluster_match_traces(self.catalog, self.data)
        galaxy_match = {"name": "Catalog match: NED", "meta": {"kind": "catalog_match"}}
        preserved = [galaxy_match] + tcc._as_json({"data": traces})["data"]
        self.assertIs(creator._refresh_cluster_matches(preserved, self.data), preserved)

        amico = _data_near(self.catalog.df, "AMICO")
        out = creator._refresh_cluster_matches(preserved, amico, (50.0, 60.0, -55.0, -45.0))
        self.assertIs(out[0], galaxy_match)
        self.assertEqual([t.meta["algorithm"] for t in out[1:]], ["AMICO", "AMICO"])

        # A catalog removed meanwhile loses its links
        self.registry.remove(self.cid)
        self.assertEqual(creator._refresh_cluster_matches(preserved, amico), [galaxy_match])


class ClusterMatchCallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.spt = _spt_fits(self.tmp.name)
        self.registry = CatalogRegistry(
            os.path.join(self.tmp.name, "catalogs.json"),
            cache_dir=os.path.join(self.tmp.name, "cache"),
        )
        self.cid = self.registry.add(
            CatalogSpec("SPT-3G", self.spt, dict(SPT_MAPPING), kind=CLUSTER)
        )
        catalog = self.registry.catalog(self.cid)
        catalog.load()
        self.data = _data_near(catalog.df)
        loader = SimpleNamespace(load_data=lambda algorithm: dict(self.data, algorithm=algorithm))
        self.app = dash.Dash(__name__)
        self.app.layout = tcc.AppLayout.create_layout()
        cc.CatalogCallbacks(
            self.app, self.registry, SimpleNamespace(current_catred_data={}), loader
        )
        self.fn = {}
        for value in self.app.callback_map.values():
            fn = value.get("callback")
            if fn is not None:
                fn = getattr(fn, "__wrapped__", fn)
                self.fn[fn.__name__] = fn

    def tearDown(self):
        self.tmp.cleanup()

    def _shown(self, ids, values):
        figure, _ = tcc._call(
            self.fn["show_catalogs"],
            tcc._pid("catalog-show", ids[0]["index"], "value"),
            True,
            values,
            ids,
            [""] * len(ids),
            tcc._cluster_figure(),
            None,
            None,
        )
        return tcc._as_json(figure)

    def test_cross_match_button(self):
        ids = [{"type": "catalog-show", "index": self.cid}]
        match = self.fn["cross_match_cluster_catalogs"]
        out = match(1, "PZWAV", None, tcc._cluster_figure(), [False], ids)
        self.assertEqual(out[1], "Show a cluster catalog first.")

        figure = self._shown(ids, [True])
        figure, feedback = match(1, "PZWAV", None, figure, [True], ids)
        self.assertIn("SPT-3G: 2 of 5 matched (PZWAV", feedback)
        kinds = [TraceRegistry.classify_trace(t) for t in figure["data"]]
        expected = [TraceType.GALAXY_CATALOG] + [TraceType.CATALOG_MATCH] * 2 + [TraceType.CLUSTER]
        self.assertEqual(kinds, expected)
        # Again with another algorithm: replaced, not added
        figure, feedback = match(1, "AMICO", None, tcc._as_json(figure), [True], ids)
        self.assertIn("(AMICO", feedback)
        self.assertEqual([TraceRegistry.classify_trace(t) for t in figure["data"]], expected)

    def test_catred_matches_keep_cluster_links(self):
        ned = self.registry.add(
            CatalogSpec("NED", tcc._ned_fits(self.tmp.name), {"RA": "RA", "DEC": "DEC"})
        )
        ids = [{"type": "catalog-show", "index": c} for c in (self.cid, ned)]
        figure = self._shown(ids, [True, True])
        figure, _ = self.fn["cross_match_cluster_catalogs"](
            1, "PZWAV", None, figure, [True, True], ids
        )
        scatter = {"ra": [33.8], "dec": [-52.2], "phz_pdf": [[1.0]], "phz_median": [0.3]}
        result = tcc.CatalogMatchResult(
            catred_scatter=scatter,
            catred_ra=np.array([33.8]),
            catred_dec=np.array([-52.2]),
            display_matched_idx=np.array([0]),
            rows=pd.DataFrame(),
            overall_nearest_arcsec=0.1,
            display_galaxy_idx=np.array([0]),
        )
        with (
            tcc.mock.patch.object(cc, "match_by_position", return_value=result),
            tcc.mock.patch.object(cc, "write_matches"),
        ):
            figure, feedback = self.fn["load_catred_near_catalogs"](
                1, 3.0, "PZWAV", True, 0.8, 24, None, tcc._as_json(figure), [True, True], ids
            )
        self.assertIn("NED: 1 CATRED sources", feedback)
        names = [t["name"] if isinstance(t, dict) else t.name for t in figure["data"]]
        self.assertIn("Catalog match: SPT-3G ↔ Euclid PZWAV", names)
        self.assertIn("Catalog match: NED", names)


class ClusterCatalogFilterTest(unittest.TestCase):
    """'Clusters with (or without) a match in' a cluster catalog: by cross-match."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = CatalogRegistry(
            os.path.join(self.tmp.name, "catalogs.json"),
            cache_dir=os.path.join(self.tmp.name, "cache"),
        )
        self.spt = self.registry.add(
            CatalogSpec("SPT-3G", _spt_fits(self.tmp.name), dict(SPT_MAPPING), kind=CLUSTER)
        )
        catalog = self.registry.catalog(self.spt)
        catalog.load()
        self.data = _data_near(catalog.df)  # SPT counterparts: Euclid IDs 11, 22, 44
        self.creator = TraceCreator(catalog_registry=self.registry)

    def tearDown(self):
        self.tmp.cleanup()

    def _ids(self, catalog_ids, mode="with"):
        rows = self.creator._prefilter_merged(
            self.data, catalog_filter_ids=catalog_ids, catalog_filter_mode=mode
        )
        return sorted(rows["ID_UNIQUE_CLUSTER"])

    def test_with_and_without_a_match(self):
        self.assertEqual(self._ids([]), [11, 22, 33, 44])
        self.assertEqual(self._ids([self.spt]), [11, 22, 44])
        self.assertEqual(self._ids([self.spt], "without"), [33])
        # Matches follow the loaded algorithm's merged catalog
        self.data["algorithm"] = "AMICO"
        self.data["data_detcluster_mergedcat"]["RIGHT_ASCENSION_CLUSTER"][0] += 1.0
        self.assertEqual(self._ids([self.spt]), [22, 44])

    def test_union_with_a_galaxy_catalog(self):
        galaxies = os.path.join(self.tmp.name, "galaxies.csv")
        with open(galaxies, "w") as f:
            f.write("ra,dec,cluster_id\n10,0,33\n")
        gid = self.registry.add(
            CatalogSpec("Gal", galaxies, {"RA": "ra", "DEC": "dec", "CLUSTER_ID": "cluster_id"})
        )
        self.assertEqual(self._ids([self.spt, gid]), [11, 22, 33, 44])
        self.assertEqual(self._ids([self.spt, gid], "without"), [])

    def test_filter_states_follow_the_resolver(self):
        import inspect

        from cluster_visualization.callbacks.main_plot import FILTER_STATES, MainPlotCallbacks

        params = inspect.signature(MainPlotCallbacks._resolve_filter_kwargs).parameters
        self.assertEqual(len(FILTER_STATES), len(params))
        self.assertEqual(
            [s.component_id for s in FILTER_STATES[-2:]],
            ["catalog-filter-dropdown", "catalog-filter-mode"],
        )
        self.assertEqual(list(params)[-2:], ["catalog_filter_ids", "catalog_filter_mode"])

    def test_dropdown_offers_cluster_catalogs(self):
        app = dash.Dash(__name__)
        app.layout = tcc.AppLayout.create_layout()
        cc.CatalogCallbacks(app, self.registry)
        fn = next(
            v["callback"]
            for k, v in app.callback_map.items()
            if "catalog-filter-dropdown.options" in k
        )
        options, _, disabled, help_text = getattr(fn, "__wrapped__", fn)(1, [])
        self.assertEqual(
            options, [{"label": "SPT-3G (5 clusters, by cross-match)", "value": self.spt}]
        )
        self.assertFalse(disabled)
        self.assertIn("by cross-match", help_text)


class ClusterCardCounterpartsTest(unittest.TestCase):
    """'Known counterparts' in the selected-cluster card."""

    def setUp(self):
        from cluster_visualization.callbacks.cluster_modal_callbacks import ClusterModalCallbacks

        self.tmp = tempfile.TemporaryDirectory()
        self.registry = CatalogRegistry(
            os.path.join(self.tmp.name, "catalogs.json"),
            cache_dir=os.path.join(self.tmp.name, "cache"),
        )
        self.card = ClusterModalCallbacks.__new__(ClusterModalCallbacks)
        self.card.trace_creator = SimpleNamespace(catalog_registry=self.registry)

    def tearDown(self):
        self.tmp.cleanup()

    def _card(self, ra, dec, z):
        record = {"Z_CLUSTER": z, "ID_UNIQUE_CLUSTER": 11}
        content = self.card._build_cluster_tab_content(
            ra, dec, "10.00", f"{z}", "PZWAV", 11, "", merged_record=record
        )
        return str(content)

    def test_no_cluster_catalog_no_entry(self):
        self.assertNotIn("Known counterparts", self._card(54.0, -51.0, 0.76))

    def test_counterparts_listed(self):
        cid = self.registry.add(
            CatalogSpec(
                "SPT-3G",
                _spt_fits(self.tmp.name),
                dict(SPT_MAPPING),
                kind=CLUSTER,
                units={"MASS": "1e+14solMass"},
            )
        )
        df = self.registry.catalog(cid).get_all()
        text = self._card(df["RA"][0], df["DEC"][0] + 0.5 / 60.0, 0.76)
        self.assertIn("Known counterparts", text)
        self.assertIn(
            "SPT-3G: SPT-CL J0330-5046, z 0.750, 0.50′, Δz/(1+z) 0.006, "
            "mass 3.7 [1e+14solMass], richness 189, SNR 4.5",
            text,
        )
        # Too far in redshift, then too far away
        self.assertIn("SPT-3G: none within 2′", self._card(df["RA"][0], df["DEC"][0], 1.5))
        self.assertIn("SPT-3G: none within 2′", self._card(100.0, 0.0, 0.76))
        # Without a Euclid redshift: by position
        self.assertIn("0.00′, by position", self._card(df["RA"][1], df["DEC"][1], float("nan")))

    def test_unavailable_catalog_shows_its_status(self):
        self.registry.add(
            CatalogSpec(
                "Gone",
                os.path.join(self.tmp.name, "gone.fits"),
                {"RA": "a", "DEC": "b"},
                kind=CLUSTER,
            )
        )
        self.assertIn("Gone: file not found", self._card(54.0, -51.0, 0.76))


if __name__ == "__main__":
    unittest.main()
