"""Cluster redraws outside a render (CATRED load, CATRED box) use the render's filters and
view window, and BOTH-algorithm matching keeps only matched pairs with CATRED on the map."""

import tempfile
import unittest
from unittest import mock

import dash
import diskcache

from cluster_visualization.callbacks.catred_callbacks import CATREDCallbacks
from cluster_visualization.callbacks.cluster_modal_callbacks import ClusterModalCallbacks
from cluster_visualization.callbacks.main_plot import FILTER_STATES, cull_settings
from cluster_visualization.src.visualization.traces import TraceCreator
from cluster_visualization.tests.test_incremental_render import make_data
from cluster_visualization.ui.layout import AppLayout

FAR_CATRED = [(10.0, 10.0)]  # CATRED loaded, but near none of the clusters


def _marker_count(traces):
    """Clusters drawn as markers (outlines, glows and ovals not counted)."""
    n = 0
    for t in traces:
        name = t.name or ""
        if (t.meta or {}).get("outline") or "in CATRED region" in name or name == "Matched Pair":
            continue
        if "Merged" in name and t.x is not None:
            n += len(t.x)
    return n


class MatchingWithCatredTest(unittest.TestCase):
    def setUp(self):
        self.data = make_data(n=400)
        self.data["data_detcluster_mergedcat"]["CROSS_ID_CLUSTER"][:100] = 1.0

    def test_matched_pairs_only_with_and_without_catred(self):
        without = TraceCreator().create_cluster_traces(self.data, matching_clusters=True)
        creator = TraceCreator()
        with_catred = creator.create_cluster_traces(
            self.data, matching_clusters=True, catred_points=FAR_CATRED
        )
        self.assertEqual(_marker_count(without), 100)
        self.assertEqual(_marker_count(with_catred), 100)
        self.assertEqual(len(creator.selected_clusters(self.data, matching_clusters=True)), 100)
        ovals = lambda traces: [t for t in traces if t.name == "Matched Pair"]
        self.assertEqual(len(ovals(with_catred)), len(ovals(without)))

    def test_switch_off_draws_all(self):
        traces = TraceCreator().create_cluster_traces(self.data, catred_points=FAR_CATRED)
        self.assertEqual(_marker_count(traces), 400)


class CullSettingsTest(unittest.TestCase):
    def test_bounds_only_for_culled_catalogs(self):
        store = {"sent": [50.0, 51.0, -29.0, -28.0]}
        with mock.patch.dict(TraceCreator.VIEW_SETTINGS, {"cull_min_clusters": 100}):
            self.assertEqual(
                cull_settings(TraceCreator(), make_data(n=400), store),
                ((50.0, 51.0, -29.0, -28.0), True),
            )
            self.assertEqual(cull_settings(TraceCreator(), make_data(n=50), store), (None, False))


class RedrawWiringTest(unittest.TestCase):
    """The CATRED load and CATRED box callbacks read every filter and the view window."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        manager = dash.DiskcacheManager(diskcache.Cache(cls.tmp.name))
        cls.app = dash.Dash(__name__, background_callback_manager=manager)
        cls.app.layout = AppLayout.create_layout()
        CATREDCallbacks(cls.app, mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock())
        ClusterModalCallbacks(
            cls.app, mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _states(self, trigger):
        for spec in self.app.callback_map.values():
            if any(i["id"] == trigger for i in spec["inputs"]):
                return [(s["id"], s["property"]) for s in spec["state"]]
        self.fail(f"no callback triggered by {trigger}")

    def test_filters_and_view_window_are_read(self):
        wanted = [(s.component_id, s.component_property) for s in FILTER_STATES]
        wanted.append(("view-bounds-store", "data"))
        for trigger in ("catred-render-button", "tab-view-catred-box"):
            states = self._states(trigger)
            for state in wanted + [("matching-clusters-switch", "value")]:
                self.assertIn(state, states, trigger)
            self.assertEqual(len(states), len(set(states)), f"{trigger}: duplicate states")

    def test_catred_wrapper_forwards_filters_and_window(self):
        callbacks = CATREDCallbacks.__new__(CATREDCallbacks)
        callbacks.trace_creator = mock.Mock()
        callbacks.create_traces(
            {},
            True,
            False,
            None,
            True,
            view_bounds=(1.0, 2.0, 3.0, 4.0),
            z_threshold_lower=0.5,
            richness_mode="zp",
        )
        kwargs = callbacks.trace_creator.create_traces.call_args.kwargs
        self.assertEqual(
            (kwargs["view_bounds"], kwargs["z_threshold_lower"], kwargs["richness_mode"]),
            ((1.0, 2.0, 3.0, 4.0), 0.5, "zp"),
        )


class CatredBoxOverCatredTest(unittest.TestCase):
    """A CATRED box keeps the CATRED loaded before it, and the p(z) click data of both."""

    def test_earlier_catred_and_its_click_data_stay(self):
        import os

        import plotly.graph_objs as go

        box = {
            "ra": [51.1, 51.2],
            "dec": [-28.1, -28.2],
            "trace_marker_size": [5, 5],
            "trace_marker_color": ["red", "red"],
            "phz_pdf": [[0.1], [0.2]],
            "phz_mode_1": [0.5, 0.6],
            "phz_median": [0.5, 0.6],
            "phz_70_int": [[0.4, 0.6], [0.5, 0.7]],
        }
        earlier = go.Scattergl(name="CATRED Masked - Tiles", x=[51.0], y=[-28.0])
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home}):
            state = os.path.join(home, ".cache", "clusterviz_state")
            with diskcache.Cache(state) as cache:  # written by the earlier CATRED load
                cache.set(
                    "catred_click_data",
                    {
                        "CATRED Masked - Tiles": {"ra": [51.0], "dec": [-28.0]},
                        "CATRED Masked - Cleared": {"ra": [1.0], "dec": [2.0]},
                    },
                )
            with mock.patch.object(TraceCreator, "_create_cltile_polygons"):
                traces = TraceCreator().create_traces(
                    make_data(),
                    True,
                    False,
                    None,
                    True,
                    catred_box_data=box,
                    existing_catred_traces=[earlier],
                )
            with diskcache.Cache(state) as cache:
                click_data = cache.get("catred_click_data")
        names = [t.name for t in traces if (t.name or "").startswith("CATRED")]
        self.assertEqual(names, ["CATRED Masked - Tiles", "CATRED Masked - Boxed"])
        # Traces no longer on the map lose their click data
        self.assertEqual(sorted(click_data), ["CATRED Masked - Boxed", "CATRED Masked - Tiles"])


if __name__ == "__main__":
    unittest.main()
