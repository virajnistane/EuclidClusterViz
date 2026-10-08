"""NED spec-z verification: catalog status, cluster filter, switch state, status count."""

import os
import tempfile
import unittest
from unittest import mock

import numpy as np
from astropy.io import fits

from cluster_visualization.callbacks.main_plot import MainPlotCallbacks
from cluster_visualization.src.data.ned_handler import NEDHandler
from cluster_visualization.src.visualization.traces import TraceCreator
from cluster_visualization.ui.sidebar_sections import SidebarSections

NED_IDS = [5, 259, 338]


class _Config:
    def __init__(self, path):
        self.path = path

    def get_ned_specz_fits(self):
        return self.path


def _ned_fits(directory):
    rows = np.zeros(5, dtype=[("ID_UNIQUE_CLUSTER", ">i8"), ("RA", ">f8"), ("DEC", ">f8"), ("Z", ">f8")])
    rows["ID_UNIQUE_CLUSTER"] = [5, 5, 259, 338, 338]  # several galaxies per cluster
    path = os.path.join(directory, "ned.fits")
    fits.BinTableHDU(rows).writeto(path)
    return path


def _merged(n=1000):
    merged = np.zeros(n, dtype=[("ID_UNIQUE_CLUSTER", "i8"), ("Z_CLUSTER", "f8"), ("SNR_CLUSTER", "f8")])
    merged["ID_UNIQUE_CLUSTER"] = np.arange(n)
    merged["Z_CLUSTER"] = 0.5
    merged["SNR_CLUSTER"] = 10.0
    return merged


def _kwargs(ned_on):
    return MainPlotCallbacks._resolve_filter_kwargs(
        None, None, True, True, None, True, None, None, True, True,
        None, None, None, None, None, ned_specz_filter=ned_on,
    )


class TestNEDHandlerStatus(unittest.TestCase):
    def test_loaded(self):
        handler = NEDHandler(_Config(_ned_fits(tempfile.mkdtemp())))
        self.assertTrue(handler.is_available())
        self.assertEqual(handler.status, "3 clusters, 5 spec-z galaxies")

    def test_missing_file(self):
        handler = NEDHandler(_Config("/nonexistent/ned.fits"))
        self.assertFalse(handler.is_available())
        self.assertEqual(handler.status, "file not found: /nonexistent/ned.fits")

    def test_not_configured(self):
        handler = NEDHandler(_Config(None))
        self.assertFalse(handler.is_available())
        self.assertIn("not configured", handler.status)


class TestNEDPerAlgorithmCounts(unittest.TestCase):
    def test_counts_by_detection_code(self):
        rows = np.zeros(4, dtype=[("ID_UNIQUE_CLUSTER", ">i8"), ("DET_CODE_NB", ">i4")])
        rows["ID_UNIQUE_CLUSTER"] = [5, 5, 259, 338]
        rows["DET_CODE_NB"] = [1, 1, 1, 2]  # 2 AMICO clusters, 1 PZWAV
        path = os.path.join(tempfile.mkdtemp(), "ned.fits")
        fits.BinTableHDU(rows).writeto(path)
        handler = NEDHandler(_Config(path))
        self.assertEqual(handler.status, "3 clusters (AMICO 2, PZWAV 1), 4 spec-z galaxies")


class TestNEDFilter(unittest.TestCase):
    def setUp(self):
        self.data = {"data_detcluster_mergedcat": _merged(), "paths": {"use_gluematchcat": True},
                     "algorithm": "PZWAV"}

    def _selected(self, handler, ned_on):
        return TraceCreator(ned_handler=handler).selected_clusters(self.data, **_kwargs(ned_on))

    def test_filter_reduces_to_ned_clusters(self):
        handler = NEDHandler(_Config(_ned_fits(tempfile.mkdtemp())))
        self.assertEqual(len(self._selected(handler, False)), 1000)
        self.assertEqual(sorted(self._selected(handler, True)["ID_UNIQUE_CLUSTER"]), NED_IDS)

    def test_filter_without_catalog_is_noop_and_says_so(self):
        handler = NEDHandler(_Config("/nonexistent/ned.fits"))
        with mock.patch("builtins.print") as printed:
            rows = self._selected(handler, True)
        self.assertEqual(len(rows), 1000)
        self.assertTrue(any("no catalog is loaded" in str(c) for c in printed.call_args_list))

    def test_status_count_follows_filter(self):
        handler = NEDHandler(_Config(_ned_fits(tempfile.mkdtemp())))
        callbacks = MainPlotCallbacks.__new__(MainPlotCallbacks)
        callbacks.trace_creator = TraceCreator(ned_handler=handler)
        self.assertEqual(callbacks._count_selected(self.data, _kwargs(True), fallback=999), 3)
        self.assertEqual(callbacks._count_selected(self.data, _kwargs(False), fallback=999), 1000)
        callbacks.trace_creator = None
        self.assertEqual(callbacks._count_selected(self.data, _kwargs(True), fallback=999), 999)


class TestNEDSwitch(unittest.TestCase):
    def _switch_and_help(self, available, status):
        section = SidebarSections.create_ned_specz_filter_section(available, status)
        switch = section.children[1]
        help_text = section.children[3].children
        return switch, help_text

    def test_enabled_when_loaded(self):
        switch, help_text = self._switch_and_help(True, "3 clusters, 5 spec-z galaxies")
        self.assertFalse(switch.disabled)
        self.assertIn("3 clusters", help_text)

    def test_disabled_with_reason_when_missing(self):
        switch, help_text = self._switch_and_help(False, "file not found: /x/ned.fits")
        self.assertTrue(switch.disabled)
        self.assertIn("file not found: /x/ned.fits", help_text)


if __name__ == "__main__":
    unittest.main()
