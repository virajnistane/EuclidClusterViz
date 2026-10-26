"""Switching algorithm (e.g. PZWAV to BOTH): the redraw is not cut by the previous
catalog's slider ranges, pans and Apply never rebuild a map they cannot patch, and BOTH
loads with an empty algorithm or with merged catalogs of different columns."""

import tempfile
import unittest
from unittest import mock

import dash
import diskcache
import numpy as np
from dash._callback_context import context_value
from dash._utils import AttributeDict

from cluster_visualization.callbacks.main_plot import MainPlotCallbacks
from cluster_visualization.src.data.loader import _concatenate_common_columns, _snr_range
from cluster_visualization.src.visualization.figures import FigureManager
from cluster_visualization.src.visualization.traces import TraceCreator
from cluster_visualization.tests.test_incremental_render import make_data
from cluster_visualization.ui.layout import AppLayout


def _cluster_count(figure):
    n = 0
    for t in figure.data:
        name = t.name or ""
        if (t.meta or {}).get("outline") or "in CATRED region" in name:
            continue
        if "Merged" in name and t.x is not None:
            n += len(t.x)
    return n


class AlgorithmSwitchCallbacksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        manager = dash.DiskcacheManager(diskcache.Cache(cls.tmp.name))
        cls.app = dash.Dash(__name__, background_callback_manager=manager)
        cls.app.layout = AppLayout.create_layout()
        cls.data = make_data(n=400)
        cls.data["algorithm"] = "BOTH"
        cls.loader = mock.Mock()
        cls.loader.load_data.return_value = cls.data
        cls.callbacks = MainPlotCallbacks(
            cls.app, cls.loader, None, TraceCreator(), FigureManager()
        )
        cls.specs = {}
        for spec in cls.app.callback_map.values():
            if "callback" not in spec:  # clientside
                continue
            fn = spec["callback"]
            cls.specs[getattr(fn, "__wrapped__", fn).__name__] = spec

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.loader.load_data.reset_mock()

    def _call(self, name, trigger, values):
        """Run callback ``name`` as Dash would, ``trigger`` ("id.prop") firing, with
        ``values`` ({(id, prop): value}) for its inputs and states (others None)."""
        spec = self.specs[name]
        fn = spec["callback"]
        fn = getattr(fn, "__wrapped__", fn)
        args = [values.get((d["id"], d["property"])) for d in spec["inputs"] + spec["state"]]
        token = context_value.set(
            AttributeDict(triggered_inputs=[{"prop_id": trigger, "value": 1}])
        )
        try:
            return fn(*args)
        finally:
            context_value.reset(token)

    # -- redraw on algorithm change ---------------------------------------------

    def _options(self, trigger):
        values = {
            ("algorithm-dropdown", "value"): "BOTH",
            ("render-button", "n_clicks"): 1,
            ("polygon-switch", "value"): True,
            ("cltile-info-switch", "value"): False,
            ("catred-mode-switch", "value"): True,
            # As recorded at the last PZWAV render: the AMICO slider held its placeholder
            # and the ranges are PZWAV's
            ("applied-filters-store", "data"): {
                "snr-range-slider-pzwav": [10.0, 20.0],
                "snr-range-slider-amico": [0, 5],
                "redshift-range-slider": [0.5, 0.8],
            },
        }
        with mock.patch.object(TraceCreator, "_create_cltile_polygons"):
            return self._call("update_plot_options", trigger, values)

    def test_new_algorithm_drawn_without_previous_ranges(self):
        figure = self._options("algorithm-dropdown.value")[0]
        self.assertEqual(_cluster_count(figure), 400)

    def test_display_option_keeps_applied_ranges(self):
        figure = self._options("polygon-switch.value")[0]
        self.assertLess(_cluster_count(figure), 100)

    # -- Apply / pan with no patchable map --------------------------------------

    def _apply(self, trigger, rendered_algorithm):
        values = {
            ("apply-filters-button", "n_clicks"): 1,
            ("viewport-request", "data"): 3,
            ("algorithm-dropdown", "value"): "BOTH",
            ("rendered-meta-store", "data"): {"algorithm": rendered_algorithm, "cull": True},
            ("cluster-trace-index-store", "data"): {"cluster": [0], "n": 5},
            ("render-full-request", "data"): 4,
        }
        return self._call("apply_filters", trigger, values)

    def test_pan_waits_for_the_new_algorithm(self):
        figure, status, meta, ack, full = self._apply("viewport-request.data", "PZWAV")
        self.assertIs(figure, dash.no_update)
        self.assertIs(full, dash.no_update)
        self.assertEqual(ack["id"], 3)  # the browser stops waiting
        self.loader.load_data.assert_not_called()

    def test_apply_asks_for_a_full_render(self):
        figure, _, _, _, full = self._apply("apply-filters-button.n_clicks", "PZWAV")
        self.assertIs(figure, dash.no_update)  # nothing rebuilt here (overlays kept)
        self.assertEqual(full, 5)

    def test_same_algorithm_is_patched(self):
        figure, _, _, _, full = self._apply("apply-filters-button.n_clicks", "BOTH")
        self.assertIsInstance(figure, dash.Patch)
        self.assertIs(full, dash.no_update)


class BothLoadingTest(unittest.TestCase):
    def test_snr_range_of_missing_algorithm(self):
        rows = np.zeros(0, dtype=[("SNR_CLUSTER", "f8")])
        self.assertEqual(_snr_range(rows), (None, None))
        rows = np.array([(3.0,), (7.5,)], dtype=[("SNR_CLUSTER", "f8")])
        self.assertEqual(_snr_range(rows), (3.0, 7.5))

    def test_catalogs_with_different_columns_join_on_common_ones(self):
        pzwav = np.zeros(2, dtype=[("RA", ">f8"), ("SNR_CLUSTER", ">f4"), ("DET_CODE_NB", "<i4")])
        pzwav["DET_CODE_NB"] = 2
        amico = np.zeros(
            3,
            dtype=[
                ("RA", ">f8"),
                ("LAMBDA", ">f8"),
                ("SNR_CLUSTER", ">f8"),
                ("DET_CODE_NB", "<i4"),
            ],
        )
        amico["DET_CODE_NB"] = 1
        joined = _concatenate_common_columns([pzwav, amico])
        self.assertEqual(joined.dtype.names, ("RA", "SNR_CLUSTER", "DET_CODE_NB"))
        self.assertEqual(joined["DET_CODE_NB"].tolist(), [2, 2, 1, 1, 1])


if __name__ == "__main__":
    unittest.main()
