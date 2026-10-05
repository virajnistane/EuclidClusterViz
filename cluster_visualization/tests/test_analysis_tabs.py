"""
Analysis-tab behaviour that can be checked without a browser.

- Quick-tag buttons carry their own tag; the panel button uses the selected tag.
- The p(z) plot states its assumed redshift grid and marks mode and median with
  labelled lines (not colour alone); the error plot builds without raising.
- Plot clicks switch to the p(z) tab only for stored CATRED/Members traces, not for
  cluster markers whose trace name happens to mention CATRED.
"""

import unittest
from unittest import mock

import dash
import numpy as np

from cluster_visualization.callbacks.cluster_modal_callbacks import ClusterModalCallbacks
from cluster_visualization.callbacks.phz_callbacks import PHZCallbacks


class TestQuickTagRouting(unittest.TestCase):
    def test_quick_buttons_carry_their_tag(self):
        route = ClusterModalCallbacks._tag_from_trigger
        self.assertEqual(route("tab-quick-tag-good", None), "good")
        self.assertEqual(route("tab-quick-tag-bad", "good"), "bad")
        self.assertEqual(route("tab-quick-tag-dubious", None), "dubious")

    def test_panel_button_uses_selected_tag(self):
        route = ClusterModalCallbacks._tag_from_trigger
        self.assertEqual(route("tab-tag-button", "bad"), "bad")
        self.assertIsNone(route("tab-tag-button", None))


class TestTagToggle(unittest.TestCase):
    def setUp(self):
        self.cb = ClusterModalCallbacks.__new__(ClusterModalCallbacks)
        self.record = {"ID_UNIQUE_CLUSTER": 42, "RIGHT_ASCENSION_CLUSTER": 50.0, "DECLINATION_CLUSTER": -28.0}
        self.rows = [dict(self.record, cluster_tag="good")]

    def test_quick_tag_on_current_tag_removes_it(self):
        self.assertEqual(self.cb._resolve_tag_action("tab-quick-tag-good", None, "good"), "none")
        self.assertEqual(self.cb._resolve_tag_action("tab-quick-tag-bad", None, "good"), "bad")

    def test_panel_button_never_toggles(self):
        self.assertEqual(self.cb._resolve_tag_action("tab-tag-button", "good", "good"), "good")
        self.assertEqual(self.cb._resolve_tag_action("tab-tag-button", "none", "good"), "none")

    def test_current_tag_and_removal(self):
        self.assertEqual(self.cb._current_tag(self.rows, self.record), "good")
        self.assertIsNone(self.cb._current_tag(self.rows, {"ID_UNIQUE_CLUSTER": 7}))
        self.assertEqual(self.cb._remove_tagged_row(self.rows, self.record), [])


class TestPhzPlot(unittest.TestCase):
    def setUp(self):
        self.phz = PHZCallbacks.__new__(PHZCallbacks)

    def test_pdf_plot_states_grid_and_labels_lines(self):
        pdf = list(np.exp(-0.5 * ((np.linspace(0, 3, 301) - 1.1) / 0.1) ** 2))
        fig = self.phz._create_phz_pdf_plot(pdf, 52.123456, -28.5, 1.1, 1.12)
        self.assertIn("assumed", fig.layout.xaxis.title.text)
        self.assertIn("301 bins", fig.layout.xaxis.title.text)
        names = [trace.name for trace in fig.data]
        self.assertEqual(names[0], "p(z)")
        self.assertTrue(any(n.startswith("Mode") for n in names))
        self.assertTrue(any(n.startswith("Median") for n in names))
        dashes = {trace.line.dash for trace in fig.data[1:]}
        self.assertEqual(len(dashes), 2)

    def test_error_plot_builds(self):
        fig = self.phz._create_error_phz_plot("boom")
        self.assertIn("boom", fig.layout.annotations[0].text)
        self.assertFalse(fig.layout.xaxis.visible)


class _CapturingApp:
    """Stand-in for dash.Dash that keeps registered callbacks by function name."""

    def __init__(self):
        self.callbacks = {}

    def callback(self, *args, **kwargs):
        def register(func):
            self.callbacks[func.__name__] = func
            return func

        return register


class _FakeCache:
    """diskcache.Cache stand-in backed by a dict."""

    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, key, default=None):
        return self.store.get(key, default)


class TestPhzClickRouting(unittest.TestCase):
    """Only clicks on stored CATRED/Members traces switch to the p(z) tab."""

    CATRED_TRACE = "CATRED Masked - MER Tile"
    # Real cluster trace name: contains "CATRED" but is not a CATRED trace
    CLUSTER_TRACE = "PZWAV (Merged, near CATRED)"

    def setUp(self):
        catred = {
            "ra": [46.1466, 46.20],
            "dec": [-56.0432, -56.10],
            "phz_pdf": [list(np.ones(301)), list(np.ones(301))],
            "phz_mode_1": [1.0, 0.5],
            "phz_median": [1.0, 0.5],
        }
        self.catred = catred
        self.handler = type("Handler", (), {"current_catred_data": {self.CATRED_TRACE: catred}})()
        app = _CapturingApp()
        PHZCallbacks(app, catred_handler=self.handler)
        self.on_click = app.callbacks["update_phz_pdf_plot"]
        self.figure = {"data": [{"name": self.CATRED_TRACE}, {"name": self.CLUSTER_TRACE}]}
        # Shared state cache written by the background render worker; never the real one
        self.state_cache = {}
        patcher = mock.patch("diskcache.Cache", side_effect=lambda *_a, **_k: _FakeCache(self.state_cache))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _click(self, curve_number, point_number, x, y):
        point = {"curveNumber": curve_number, "pointNumber": point_number, "x": x, "y": y}
        return self.on_click({"points": [point]}, self.figure)

    def test_cluster_click_near_catred_source_leaves_tabs(self):
        # Cluster marker ~1 arcsec from a CATRED source, pointNumber valid as a CATRED row
        result = self._click(1, 0, 46.146886, -56.043191)
        self.assertTrue(all(value is dash.no_update for value in result))

    def test_catred_click_switches_to_pz_tab(self):
        _figure, tab, subtab = self._click(0, 1, 46.20, -56.10)
        self.assertEqual((tab, subtab), ("phz-tab", "phz-catred-subtab"))

    def test_catred_tile_click_after_members_loaded(self):
        # Tile CATRED built by the render worker is only in the shared cache; loading
        # members puts a Members entry into this process's handler
        members = dict(self.catred)
        self.handler.current_catred_data = {"Members (ID 109926)": members}
        self.state_cache["catred_click_data"] = {self.CATRED_TRACE: self.catred}
        _figure, tab, subtab = self._click(0, 1, 46.20, -56.10)
        self.assertEqual((tab, subtab), ("phz-tab", "phz-catred-subtab"))


if __name__ == "__main__":
    unittest.main()
