"""
Analysis-tab behaviour that can be checked without a browser.

- Quick-tag buttons carry their own tag; the panel button uses the selected tag.
- The p(z) plot states its assumed redshift grid and marks mode and median with
  labelled lines (not colour alone); the error plot builds without raising.
"""

import unittest

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


if __name__ == "__main__":
    unittest.main()
