"""Galaxy catalogs section callbacks, called directly (no browser): list, Add/Edit
dialog, show/hide, large-catalog windowing, remove, CATRED matches and the p(z) click."""

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import dash
import numpy as np
import pandas as pd
import plotly
from astropy.io import fits
from dash._callback_context import context_value
from dash._utils import AttributeDict
from dash.exceptions import PreventUpdate

import cluster_visualization.callbacks.catalog_callbacks as cc
from cluster_visualization.callbacks.phz_callbacks import PHZCallbacks
from cluster_visualization.src.data.catalog_matcher import CatalogMatchResult
from cluster_visualization.src.data.catalog_registry import CatalogRegistry
from cluster_visualization.src.data.galaxy_catalog import CatalogSpec
from cluster_visualization.src.visualization import catalog_traces
from cluster_visualization.src.visualization.trace_registry import TraceRegistry, TraceType
from cluster_visualization.ui.layout import AppLayout


def _ned_fits(directory, n=6):
    rows = np.zeros(
        n, dtype=[("ID_UNIQUE_CLUSTER", ">i8"), ("RA", ">f8"), ("DEC", ">f8"), ("Z", ">f8")]
    )
    rows["ID_UNIQUE_CLUSTER"] = [5, 5, 259, 338, 338, 338]
    rows["RA"] = np.linspace(33.7, 33.9, n)
    rows["DEC"] = np.linspace(-52.3, -52.1, n)
    rows["Z"] = 0.48
    path = os.path.join(directory, "ned.fits")
    fits.BinTableHDU(rows).writeto(path)
    return path


def _two_table_fits(directory):
    a = np.zeros(3, dtype=[("ra", ">f8"), ("dec", ">f8")])
    a["ra"], a["dec"] = [10.0, 10.1, 10.2], [-5.0, -5.1, -5.2]
    b = np.zeros(2, dtype=[("RAJ2000", ">f8"), ("DEJ2000", ">f8"), ("zspec", ">f4")])
    b["RAJ2000"], b["DEJ2000"] = [20.0, 20.1], [1.0, 1.1]
    path = os.path.join(directory, "two.fits")
    fits.HDUList(
        [fits.PrimaryHDU(), fits.BinTableHDU(a, name="A"), fits.BinTableHDU(b, name="B")]
    ).writeto(path)
    return path


def _call(fn, prop_id, value, *args):
    """Run a callback function as Dash would, with ``prop_id`` as the trigger."""
    token = context_value.set(
        AttributeDict(triggered_inputs=[{"prop_id": prop_id, "value": value}])
    )
    try:
        return fn(*args)
    finally:
        context_value.reset(token)


def _pid(type_, index, prop):
    return json.dumps({"index": index, "type": type_}, separators=(",", ":")) + "." + prop


def _as_json(figure):
    """The figure as the browser sends it back (plain dicts and lists)."""
    return json.loads(json.dumps(figure, cls=plotly.utils.PlotlyJSONEncoder))


def _cluster_figure():
    return {
        "data": [
            {"type": "scattergl", "name": "PZWAV (Merged) 10 clusters", "x": [33.8], "y": [-52.2]}
        ],
        "layout": {"xaxis": {"range": [33.5, 34.0]}, "yaxis": {"range": [-52.5, -52.0]}},
    }


class CatalogCallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.ned = _ned_fits(self.dir)
        self.registry = CatalogRegistry(
            os.path.join(self.dir, "catalogs.json"), cache_dir=os.path.join(self.dir, "cache")
        )
        self.catred = SimpleNamespace(current_catred_data={"Members (ID 7)": {"ra": [1.0]}})
        self.loader = SimpleNamespace(load_data=lambda algorithm: {})
        self.app = dash.Dash(__name__)
        self.app.layout = AppLayout.create_layout()
        cc.CatalogCallbacks(self.app, self.registry, self.catred, self.loader)
        self.fn = {}
        for value in self.app.callback_map.values():
            fn = value.get("callback")  # clientside callbacks have none
            if fn is None:
                continue
            fn = getattr(fn, "__wrapped__", fn)
            self.fn[fn.__name__] = fn

    def tearDown(self):
        self.tmp.cleanup()

    def _add_ned(self, name="NED spec-z"):
        return self.registry.add(
            CatalogSpec(
                name,
                self.ned,
                {"RA": "RA", "DEC": "DEC", "SPEC_Z": "Z", "CLUSTER_ID": "ID_UNIQUE_CLUSTER"},
            )
        )

    # -- list and dialog -------------------------------------------------------

    def test_list(self):
        self.assertIn("No catalogs yet", str(self.fn["render_catalog_list"](0, [], [])))
        cid = self._add_ned()
        rows = self.fn["render_catalog_list"](1, [True], [{"type": "catalog-show", "index": cid}])
        self.assertEqual(len(rows), 1)
        text = str(rows[0])
        self.assertIn("'index': 'ned_spec_z'", text)
        self.assertIn("value=True", text)  # switch state kept across re-renders
        self.assertIn("clusters", text)  # CLUSTER_ID badge

    def test_dialog_open_edit_cancel(self):
        open_dialog = self.fn["open_catalog_dialog"]
        out = _call(open_dialog, "catalog-add-button.n_clicks", 1, 1, [], 0)
        self.assertTrue(out[0])
        self.assertEqual(out[1]["mode"], "add")
        cid = self._add_ned()
        out = _call(open_dialog, _pid("catalog-edit", cid, "n_clicks"), 1, 0, [1], 0)
        self.assertEqual((out[1]["mode"], out[1]["id"], out[3]), ("edit", cid, self.ned))
        self.assertFalse(_call(open_dialog, "catalog-cancel-button.n_clicks", 1, 0, [0], 1)[0])
        with self.assertRaises(PreventUpdate):  # list re-render: new buttons with n_clicks=0
            _call(open_dialog, _pid("catalog-edit", cid, "n_clicks"), 0, 0, [0], 0)

    def test_read_and_fill(self):
        read = self.fn["read_catalog_columns"]
        out = _call(read, "catalog-read-button.n_clicks", 1, 1, None, {"mode": "add"}, "/nope.fits")
        self.assertIsNone(out[0])
        self.assertIn("not found", str(out[4]))

        two = _two_table_fits(self.dir)
        store, options, index, hdu_style, _, section = _call(
            read, "catalog-read-button.n_clicks", 1, 1, None, {"mode": "add"}, two
        )
        self.assertEqual((len(options), index, hdu_style, section), (2, 0, cc.SHOWN, cc.SHOWN))

        fill = self.fn["fill_catalog_mapping"]
        out = _call(fill, "catalog-table-store.data", store, store, 1, {"mode": "add"})
        ra_options, ra_value = out[0], out[1]
        self.assertEqual(ra_value, "RAJ2000")
        self.assertEqual([o["value"] for o in ra_options], ["RAJ2000", "DEJ2000", "zspec"])
        self.assertEqual(out[-4:-1], ("two", "#ff8800", "diamond"))
        # Switching table keeps the name the user may have typed
        out = _call(fill, "catalog-hdu-dropdown.value", 0, store, 0, {"mode": "add"})
        self.assertEqual(out[1], "ra")
        self.assertIs(out[-4], dash.no_update)

    def test_edit_restores_saved_mapping(self):
        cid = self.registry.add(
            CatalogSpec("Mine", self.ned, {"RA": "RA", "DEC": "DEC"}, hdu=1, color="#123456")
        )
        state = {"mode": "edit", "id": cid, "spec": self.registry.get(cid).to_dict()}
        store = _call(
            self.fn["read_catalog_columns"],
            "catalog-modal-state.data",
            state,
            0,
            None,
            state,
            self.ned,
        )[0]
        out = _call(
            self.fn["fill_catalog_mapping"], "catalog-table-store.data", store, store, 0, state
        )
        roles = dict(zip([r.name for r in cc.ROLES], out[1 : 2 * len(cc.ROLES) : 2]))
        self.assertIsNone(roles["SPEC_Z"])  # the saved mapping, not the suggestion "Z"
        self.assertEqual(out[-4:-1], ("Mine", "#123456", "diamond"))

    def _save(self, trigger, store, roles, name="NED", state=None, figure=None):
        values = [roles.get(r.name) for r in cc.ROLES]
        args = [
            0,
            1,
            store,
            0,
            *values,
            None,
            [],
            name,
            "#00aa00",
            "square",
            state or {"mode": "add"},
            3,
            figure,
            None,
        ]
        return _call(self.fn["check_or_save_catalog"], f"{trigger}.n_clicks", 1, *args)

    def test_check_and_save(self):
        store = _call(
            self.fn["read_catalog_columns"],
            "catalog-read-button.n_clicks",
            1,
            1,
            None,
            {"mode": "add"},
            self.ned,
        )[0]
        feedback, is_open, _, _ = self._save(
            "catalog-check-button", store, {"RA": "RA", "DEC": "DEC"}
        )
        self.assertIs(is_open, dash.no_update)
        self.assertIn("6 rows", str(feedback))
        feedback, *_ = self._save("catalog-save-button", store, {"RA": "RA"})
        self.assertIn("required", str(feedback))
        self.assertEqual(self.registry.list(), [])

        _, is_open, version, _ = self._save(
            "catalog-save-button", store, {"RA": "RA", "DEC": "DEC", "SPEC_Z": "Z"}
        )
        self.assertEqual((is_open, version), (False, 4))
        (spec,) = self.registry.list()
        self.assertEqual(
            (spec.name, spec.columns["SPEC_Z"], spec.symbol, spec.hdu), ("NED", "Z", "square", 1)
        )
        feedback, *_ = self._save("catalog-save-button", store, {"RA": "RA", "DEC": "DEC"})
        self.assertIn("already exists", str(feedback))

    def test_edit_redraws_shown_catalog(self):
        cid = self._add_ned()
        ids = [{"type": "catalog-show", "index": cid}]
        figure = _as_json(self._show([True], ids, _cluster_figure())[0])
        state = {"mode": "edit", "id": cid, "spec": self.registry.get(cid).to_dict()}
        store = _call(
            self.fn["read_catalog_columns"],
            "catalog-modal-state.data",
            state,
            0,
            None,
            state,
            self.ned,
        )[0]
        _, is_open, _, figure = self._save(
            "catalog-save-button",
            store,
            {"RA": "RA", "DEC": "DEC"},
            name="NED renamed",
            state=state,
            figure=figure,
        )
        self.assertFalse(is_open)
        names = [t["name"] if isinstance(t, dict) else t.name for t in figure["data"]]
        self.assertEqual(names, ["Catalog: NED renamed", "PZWAV (Merged) 10 clusters"])

    # -- markers ---------------------------------------------------------------

    def _show(self, values, ids, figure):
        prop = _pid("catalog-show", ids[0]["index"], "value")
        return _call(
            self.fn["show_catalogs"], prop, values[0], values, ids, [""] * len(ids), figure, None
        )

    def test_show_hide(self):
        cid = self._add_ned()
        ids = [{"type": "catalog-show", "index": cid}]
        figure, statuses = self._show([True], ids, _cluster_figure())
        names = [t["name"] if isinstance(t, dict) else t.name for t in figure["data"]]
        self.assertEqual(
            names, ["Catalog: NED spec-z", "PZWAV (Merged) 10 clusters"]
        )  # under the clusters
        self.assertEqual(statuses, ["6 galaxies, 3 clusters"])
        figure = _as_json(figure)
        meta = figure["data"][0]["meta"]
        self.assertEqual(
            (meta["kind"], meta["catalog_id"], meta["windowed"]), ("catalog", cid, False)
        )
        self.assertIn("z_spec: 0.4800", figure["data"][0]["text"][0])
        with self.assertRaises(PreventUpdate):  # already drawn: nothing to do
            self._show([True], ids, figure)
        figure, _ = self._show([False], ids, figure)
        self.assertEqual(len(figure["data"]), 1)

    def test_missing_file_shows_status(self):
        cid = self.registry.add(
            CatalogSpec("Gone", os.path.join(self.dir, "gone.fits"), {"RA": "a", "DEC": "b"})
        )
        ids = [{"type": "catalog-show", "index": cid}]
        figure, statuses = self._show([True], ids, _cluster_figure())
        self.assertEqual(len(figure["data"]), 1)  # nothing drawn
        self.assertIn("file not found", statuses[0])

    def test_large_catalog_is_windowed(self):
        cid = self._add_ned()
        ids = [{"type": "catalog-show", "index": cid}]
        relayout = {
            "xaxis.range[0]": 33.79,
            "xaxis.range[1]": 33.81,
            "yaxis.range[0]": -52.3,
            "yaxis.range[1]": -52.1,
        }
        with mock.patch.object(catalog_traces, "DISPLAY_MAX", 3):
            _, statuses = self._show([True], ids, _cluster_figure())
            self.assertIn("drawn for the current view", statuses[0])
            payload = self.fn["window_catalogs"](relayout, [True], ids)
            (trace,) = payload["traces"]
            self.assertTrue(trace["meta"]["windowed"])
            self.assertLess(len(trace["x"]), 6)
            with self.assertRaises(PreventUpdate):  # legend click etc.: no axis change
                self.fn["window_catalogs"]({"dragmode": "pan"}, [True], ids)
        with self.assertRaises(PreventUpdate):  # small catalogs are never windowed
            self.fn["window_catalogs"](relayout, [True], ids)

    def test_remove(self):
        cid = self._add_ned()
        ids = [{"type": "catalog-show", "index": cid}]
        figure = _as_json(self._show([True], ids, _cluster_figure())[0])
        version, figure = _call(
            self.fn["remove_catalog"], _pid("catalog-remove", cid, "n_clicks"), 1, [1], 2, figure
        )
        self.assertEqual(version, 3)
        self.assertEqual([t["name"] for t in figure["data"]], ["PZWAV (Merged) 10 clusters"])
        self.assertEqual(self.registry.list(), [])

    # -- CATRED near shown catalogs ----------------------------------------------

    def test_match_and_pz_click(self):
        cid = self._add_ned()
        ids = [{"type": "catalog-show", "index": cid}]
        figure, _ = self._show([True], ids, _cluster_figure())
        n = 4
        scatter = {
            "ra": list(33.8 + np.arange(n) * 1e-4),
            "dec": [-52.2] * n,
            "phz_pdf": [[float(i)] * 10 for i in range(n)],
            "phz_mode_1": [0.1] * n,
            "phz_median": [0.2 * i for i in range(n)],
            "phz_70_int": [[0.0, 0.1]] * n,
        }
        result = CatalogMatchResult(
            catred_scatter=scatter,
            catred_ra=np.array(scatter["ra"]),
            catred_dec=np.array(scatter["dec"]),
            display_matched_idx=np.array([1, 3]),
            rows=pd.DataFrame(),
            overall_nearest_arcsec=0.1,
        )
        with (
            mock.patch.object(cc, "match_by_position", return_value=result) as match,
            mock.patch.object(cc, "write_matches") as write,
        ):
            figure, feedback = self.fn["load_catred_near_catalogs"](
                1, 3.0, "PZWAV", True, 0.8, 24, None, figure, [True], ids
            )
        self.assertEqual(
            len(match.call_args.args[0]), 6
        )  # all NED rows are inside the figure's range
        write.assert_called_once()
        self.assertIn("NED spec-z: 2 CATRED sources within 3.0″ of 6 galaxies", feedback)
        kinds = [TraceRegistry.classify_trace(t) for t in figure["data"]]
        self.assertEqual(
            kinds, [TraceType.GALAXY_CATALOG, TraceType.CATALOG_MATCH, TraceType.CLUSTER]
        )
        self.assertIn("Members (ID 7)", self.catred.current_catred_data)
        self.assertEqual(
            self.catred.current_catred_data["Catalog match: NED spec-z"]["phz_pdf"],
            [[1.0] * 10, [3.0] * 10],
        )

        app = dash.Dash(__name__)
        PHZCallbacks(app, catred_handler=self.catred)
        update = next(
            v["callback"] for k, v in app.callback_map.items() if "phz-pdf-plot.figure" in k
        )
        update = getattr(update, "__wrapped__", update)
        click = {
            "points": [{"curveNumber": 1, "pointNumber": 1, "x": scatter["ra"][3], "y": -52.2}]
        }
        plot, tab, subtab = update(click, _as_json(figure))
        self.assertEqual((tab, subtab), ("phz-tab", "phz-catred-subtab"))
        self.assertIsNot(plot, dash.no_update)

    def test_match_needs_a_shown_catalog_and_a_view(self):
        cid = self._add_ned()
        ids = [{"type": "catalog-show", "index": cid}]
        load = self.fn["load_catred_near_catalogs"]
        out = load(1, 3.0, "PZWAV", True, 0.8, 24, None, _cluster_figure(), [False], ids)
        self.assertEqual(out[1], "Show a catalog first.")
        figure = _cluster_figure()
        figure["layout"] = {}
        self.assertEqual(
            load(1, 3.0, "PZWAV", True, 0.8, 24, None, figure, [True], ids)[1], "Zoom in first."
        )


class CatalogTraceTypeTest(unittest.TestCase):
    def test_catalog_names_do_not_look_like_clusters_or_mosaics(self):
        for name in ("Catalog: AMICO members", "Catalog: Mosaic survey", "Catalog: Merged spec-z"):
            self.assertEqual(TraceRegistry.classify_trace({"name": name}), TraceType.GALAXY_CATALOG)
        self.assertEqual(
            TraceRegistry.classify_trace({"name": "Catalog match: x"}), TraceType.CATALOG_MATCH
        )

    def test_reconstruct_keeps_meta(self):
        figure = {
            "data": [
                {
                    "type": "scattergl",
                    "name": "Catalog: x",
                    "x": [1],
                    "y": [2],
                    "meta": {"kind": "catalog", "catalog_id": "x"},
                }
            ]
        }
        (trace,) = TraceRegistry.extract_traces(figure, {TraceType.GALAXY_CATALOG})[
            TraceType.GALAXY_CATALOG
        ]
        self.assertEqual(trace.meta, {"kind": "catalog", "catalog_id": "x"})


class MatcherTest(unittest.TestCase):
    def test_position_match_and_match_file(self):
        from cluster_visualization.src.data import catalog_matcher as cm

        galaxies = pd.DataFrame(
            {"SOURCE_ID": ["a", "b"], "RA": [10.0, 10.5], "DEC": [-5.0, -5.0], "SPEC_Z": [0.3, 0.4]}
        )
        scatter = {
            "ra": [10.0 + 1 / 3600 * 0.5, 10.2],
            "dec": [-5.0, -5.0],
            "phz_median": [0.31, 0.9],
            "phz_mode_1": [0.3, 0.8],
        }
        handler = SimpleNamespace(
            current_catred_data={"Members (ID 1)": {}},
            update_catred_data_with_coverage=lambda *a: dict(scatter, ra=list(scatter["ra"])),
        )
        result = cm.match_by_position(galaxies, handler, {}, radius_arcsec=2.0)
        self.assertEqual(handler.current_catred_data, {"Members (ID 1)": {}})  # restored
        self.assertEqual(result.display_matched_idx.tolist(), [0])
        (row,) = result.rows.to_dict("records")
        self.assertEqual(
            (row["SOURCE_ID"], row["MATCH_METHOD"], row["PHZ_MEDIAN"]), ("a", "position", 0.31)
        )
        self.assertAlmostEqual(row["SEP_ARCSEC"], 0.5 * np.cos(np.radians(5.0)), places=3)

        with tempfile.TemporaryDirectory() as tmp:
            spec = CatalogSpec("x", os.path.join(tmp, "cat.fits.gz"), {"RA": "ra", "DEC": "dec"})
            path = cm.write_matches(spec, result.rows)
            self.assertEqual(os.path.basename(path), "cat_catalogMatches.fits")
            again = result.rows.assign(PHZ_MEDIAN=0.5)
            cm.write_matches(spec, again)  # same SOURCE_ID: replaced, not added
            from astropy.table import Table

            table = Table.read(path)
            self.assertEqual(len(table), 1)
            self.assertAlmostEqual(float(table["PHZ_MEDIAN"][0]), 0.5)


if __name__ == "__main__":
    unittest.main()
