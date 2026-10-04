"""
Tests for the incremental "Apply filters" render path.

- TraceCreator.create_cluster_traces with the per-row cache must produce exactly
  the same traces as direct computation.
- The per-row cache is built once per loaded catalog and reused.
- The Dash Patch used to swap cluster traces records deletes (descending) before
  the append, so trace indices stay valid when applied in the browser.
"""

import json
import unittest

import numpy as np
import plotly.utils
from dash import Patch

from cluster_visualization.src.visualization.traces import TraceCreator

MERGED_DTYPE = [
    ("RIGHT_ASCENSION_CLUSTER", "f8"),
    ("DECLINATION_CLUSTER", "f8"),
    ("SNR_CLUSTER", "f8"),
    ("Z_CLUSTER", "f8"),
    ("ID_UNIQUE_CLUSTER", "i8"),
    ("DET_CODE_NB", "i4"),
    ("CROSS_ID_CLUSTER", "f8"),
    ("RICHNESS_ZP", "f8"),
    ("FLAG_QUALITY_ZP", "i4"),
    ("RICHNESS_RS", "f8"),
    ("FLAG_QUALITY_RS", "i4"),
]
TILE_DTYPE = [("RIGHT_ASCENSION_CLUSTER", "f8"), ("DECLINATION_CLUSTER", "f8")]


def make_data(n=400, seed=1):
    """Synthetic BOTH catalog: four tiles, mixed PZWAV/AMICO rows, some NaNs."""
    rng = np.random.default_rng(seed)
    merged = np.zeros(n, dtype=MERGED_DTYPE)
    merged["RIGHT_ASCENSION_CLUSTER"] = rng.uniform(50, 54, n)
    merged["DECLINATION_CLUSTER"] = rng.uniform(-30, -26, n)
    merged["SNR_CLUSTER"] = rng.uniform(2, 40, n)
    merged["Z_CLUSTER"] = rng.uniform(0.1, 2.0, n)
    merged["Z_CLUSTER"][::17] = np.nan
    merged["ID_UNIQUE_CLUSTER"] = rng.permutation(np.arange(1000, 1000 + n))
    merged["DET_CODE_NB"] = np.where(np.arange(n) % 2 == 0, 2, 1)
    merged["CROSS_ID_CLUSTER"] = np.nan
    merged["RICHNESS_ZP"] = rng.uniform(0, 100, n)
    merged["RICHNESS_ZP"][::13] = np.nan
    merged["FLAG_QUALITY_ZP"] = rng.integers(0, 3, n)
    merged["RICHNESS_RS"] = rng.uniform(0, 100, n)
    merged["FLAG_QUALITY_RS"] = rng.integers(0, 3, n)

    def tile(sel):
        t = np.zeros(sel.sum(), dtype=TILE_DTYPE)
        t["RIGHT_ASCENSION_CLUSTER"] = merged["RIGHT_ASCENSION_CLUSTER"][sel]
        t["DECLINATION_CLUSTER"] = merged["DECLINATION_CLUSTER"][sel]
        return t

    left = merged["RIGHT_ASCENSION_CLUSTER"] < 52
    pz = merged["DET_CODE_NB"] == 2
    by_cltile = {
        "1": {"tile_id": 1, "algorithm": "PZWAV", "detfits_data": tile(left & pz)},
        "2": {"tile_id": 2, "algorithm": "PZWAV", "detfits_data": tile(~left & pz)},
        "3": {"tile_id": 3, "algorithm": "AMICO", "detfits_data": tile(left & ~pz)},
        "4": {"tile_id": 4, "algorithm": "AMICO", "detfits_data": tile(~left & ~pz)},
    }
    return {
        "algorithm": "BOTH",
        "data_detcluster_mergedcat": merged,
        "data_detcluster_by_cltile": by_cltile,
        "paths": {"use_gluematchcat": True},
    }


FILTERS = dict(
    snr_threshold_lower_pzwav=5.0,
    snr_threshold_upper_pzwav=35.0,
    snr_threshold_lower_amico=3.0,
    snr_threshold_upper_amico=30.0,
    z_threshold_lower=0.3,
    z_threshold_upper=1.5,
    z_include_missing=True,
    richness_threshold_lower=10.0,
    richness_threshold_upper=90.0,
    richness_mode="zp",
    richness_include_missing=False,
    flag_quality_zp=[0, 2],
)


def as_json(traces):
    return json.dumps([t.to_plotly_json() for t in traces], cls=plotly.utils.PlotlyJSONEncoder)


class TestIncrementalRender(unittest.TestCase):
    def setUp(self):
        self.creator = TraceCreator(colors_list=["red", "blue", "green", "orange", "purple", "teal"])

    def test_cached_traces_match_direct_computation(self):
        for algorithm in ("BOTH", "PZWAV"):
            with self.subTest(algorithm=algorithm):
                data = make_data()
                data["algorithm"] = algorithm
                ids = data["data_detcluster_mergedcat"]["ID_UNIQUE_CLUSTER"][::3].tolist()
                cached = self.creator.create_cluster_traces(data, idcluster_list=ids, **FILTERS)

                direct_data = make_data()
                direct_data["algorithm"] = algorithm
                original = self.creator._row_cache_for
                self.creator._row_cache_for = lambda _data: None
                try:
                    direct = self.creator.create_cluster_traces(
                        direct_data, idcluster_list=ids, **FILTERS
                    )
                finally:
                    self.creator._row_cache_for = original

                self.assertGreater(len(cached), 0)
                self.assertEqual(as_json(cached), as_json(direct))

    def test_row_cache_built_once_per_catalog(self):
        data = make_data()
        self.creator.create_cluster_traces(data, **FILTERS)
        cache = data["_render_row_cache"]
        self.assertIsNotNone(cache)
        self.assertIsNotNone(cache["colors"])
        self.creator.create_cluster_traces(data, z_threshold_lower=0.5, z_threshold_upper=1.0)
        self.assertIs(data["_render_row_cache"], cache)

    def test_duplicate_ids_disable_cache(self):
        data = make_data()
        merged = data["data_detcluster_mergedcat"]
        merged["ID_UNIQUE_CLUSTER"][1] = merged["ID_UNIQUE_CLUSTER"][0]
        traces = self.creator.create_cluster_traces(data, **FILTERS)
        self.assertIsNone(data["_render_row_cache"])
        self.assertGreater(len(traces), 0)

    def test_patch_deletes_descending_then_appends(self):
        patch = Patch()
        for index in sorted([3, 7, 5], reverse=True):
            patch["data"].__delitem__(index)
        patch["data"].extend([{"name": "Merged PZWAV"}])
        ops = patch.to_plotly_json()["operations"]
        self.assertEqual([op["operation"] for op in ops], ["Delete", "Delete", "Delete", "Extend"])
        self.assertEqual([op["location"] for op in ops[:3]], [["data", 7], ["data", 5], ["data", 3]])



class TestRenderPreservesOverlays(unittest.TestCase):
    """Full renders carry overlays (incl. cluster members) over; cluster traces are rebuilt."""

    def test_members_catred_mask_extracted_clusters_not(self):
        from cluster_visualization.src.visualization.trace_registry import TraceRegistry, TraceType

        figure = {"data": [
            {"type": "scattergl", "name": "Merged PZWAV", "x": [1], "y": [1]},
            {"type": "scattergl", "name": "CATRED Masked - MER Tile", "x": [1], "y": [1]},
            {"type": "scatter", "name": "Mask overlay bin 0", "x": [1], "y": [1]},
            {"type": "scatter", "name": "Members (ID 42)", "x": [1], "y": [1]},
        ]}
        kept = TraceRegistry.extract_traces(
            figure, {TraceType.CATRED, TraceType.MOSAIC, TraceType.MASK_OVERLAY, TraceType.MEMBERS}
        )
        self.assertEqual(len(kept[TraceType.MEMBERS]), 1)
        self.assertEqual(len(kept[TraceType.CATRED]), 1)
        self.assertEqual(len(kept[TraceType.MASK_OVERLAY]), 1)
        names = [getattr(t, "name", None) or t.get("name") for ts in kept.values() for t in ts]
        self.assertNotIn("Merged PZWAV", names)


class TestScalingEquivalence(unittest.TestCase):
    """New vectorised paths give the same answers as the old dense / per-pair code."""

    def setUp(self):
        self.creator = TraceCreator(colors_list=["red", "blue", "green", "orange", "purple", "teal"])

    def test_kdtree_unmerged_matches_dense(self):
        rng = np.random.default_rng(3)
        merged = make_data(n=600)["data_detcluster_mergedcat"]
        tile = np.zeros(400, dtype=[("RIGHT_ASCENSION_CLUSTER", "f8"), ("DECLINATION_CLUSTER", "f8"), ("Z_CLUSTER", "f8")])
        src = merged[rng.choice(len(merged), 200, replace=False)]
        tile["RIGHT_ASCENSION_CLUSTER"][:200] = src["RIGHT_ASCENSION_CLUSTER"] + rng.normal(0, 1e-4, 200)
        tile["DECLINATION_CLUSTER"][:200] = src["DECLINATION_CLUSTER"] + rng.normal(0, 1e-4, 200)
        tile["Z_CLUSTER"][:200] = src["Z_CLUSTER"]
        tile["RIGHT_ASCENSION_CLUSTER"][200:] = rng.uniform(50, 54, 200)
        tile["DECLINATION_CLUSTER"][200:] = rng.uniform(-30, -26, 200)
        tile["Z_CLUSTER"][200:] = rng.uniform(0.1, 2.0, 200)

        new = self.creator._find_unmerged_mask(tile, merged, None)

        tol = 2.0 / 3600.0
        t_ra, t_dec, t_z = tile["RIGHT_ASCENSION_CLUSTER"], tile["DECLINATION_CLUSTER"], tile["Z_CLUSTER"]
        m_ra, m_dec, m_z = merged["RIGHT_ASCENSION_CLUSTER"], merged["DECLINATION_CLUSTER"], merged["Z_CLUSTER"]
        d = np.sqrt((t_ra[:, None] - m_ra[None, :]) ** 2 + (t_dec[:, None] - m_dec[None, :]) ** 2)
        old = ~np.any((d <= tol) & (np.abs(t_z[:, None] - m_z[None, :]) <= 0.02), axis=1)
        np.testing.assert_array_equal(new, old)

    def test_single_trace_ovals_cover_all_pairs(self):
        data = make_data(n=400)
        merged = data["data_detcluster_mergedcat"]
        pz = merged[merged["DET_CODE_NB"] == 2]
        am = merged[merged["DET_CODE_NB"] == 1]
        n_pairs = min(len(pz), len(am), 50)
        pz = pz.copy()
        pz["CROSS_ID_CLUSTER"][:n_pairs] = am["ID_UNIQUE_CLUSTER"][:n_pairs]
        trace = self.creator._matched_pair_trace(pz, am, None, n_points=48)
        self.assertEqual(trace.name, "Matched Pair")
        gaps = int(np.isnan(np.asarray(trace.x, dtype=float)).sum())
        self.assertEqual(gaps, n_pairs)  # one ellipse (+ NaN gap) per matched pair
        self.assertEqual(len(trace.x), n_pairs * 49)

    def test_no_pairs_gives_no_trace(self):
        data = make_data(n=100)
        merged = data["data_detcluster_mergedcat"]
        pz = merged[merged["DET_CODE_NB"] == 2]
        am = merged[merged["DET_CODE_NB"] == 1]
        self.assertIsNone(self.creator._matched_pair_trace(pz, am, None))


class TestViewportCulling(unittest.TestCase):
    def setUp(self):
        self.creator = TraceCreator(colors_list=["red", "blue", "green", "orange", "purple", "teal"])

    def test_cull_across_ra_zero(self):
        arr = np.zeros(4, dtype=MERGED_DTYPE)
        arr["RIGHT_ASCENSION_CLUSTER"] = [359.5, 0.5, 180.0, 1.4]
        arr["DECLINATION_CLUSTER"] = [0.0, 0.0, 0.0, 5.0]
        # RA wraps: 359.5 and 0.5 are both inside; 180 and the Dec 5 point are not
        kept = TraceCreator._cull_to_view(arr, (-1.0, 1.0, -1.0, 1.0))
        self.assertEqual(sorted(kept["RIGHT_ASCENSION_CLUSTER"].tolist()), [0.5, 359.5])
        kept = TraceCreator._cull_to_view(arr, (359.0, 361.0, -1.0, 1.0))
        self.assertEqual(sorted(kept["RIGHT_ASCENSION_CLUSTER"].tolist()), [0.5, 359.5])

    def test_cull_keeps_margin(self):
        arr = np.zeros(4, dtype=MERGED_DTYPE)
        arr["RIGHT_ASCENSION_CLUSTER"] = [46.0, 50.0, 51.2, 54.0]
        arr["DECLINATION_CLUSTER"] = [-28.0, -28.0, -28.0, -28.0]
        # 2 deg wide view + 100% margin each side: RA 47..53 kept
        kept = TraceCreator._cull_to_view(arr, (49.0, 51.0, -29.0, -27.0))
        self.assertEqual(kept["RIGHT_ASCENSION_CLUSTER"].tolist(), [50.0, 51.2])

    def test_culled_traces_only_hold_view_clusters(self):
        data = make_data(n=400)
        traces = self.creator.create_cluster_traces(data, view_bounds=(50.0, 51.0, -29.0, -28.0))
        xs = np.concatenate([np.asarray(t.x, dtype=float) for t in traces if "Merged" in (t.name or "")])
        self.assertTrue(len(xs) > 0)
        # view 50..51 with 100% margin: 49..52
        self.assertTrue(np.all((xs >= 49.0) & (xs <= 52.0)))

    def tearDown(self):
        TraceCreator.configure_view(cull_min_clusters=5000, max_points_sent=50000, density_threshold=50000)

    def test_density_above_threshold(self):
        data = make_data(n=400)
        TraceCreator.configure_view(density_threshold=100)
        traces = self.creator.create_cluster_traces(data)
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].type, "heatmap")
        self.assertIn("Merged", traces[0].name)  # still classified as a cluster trace
        self.assertEqual(int(np.nansum(np.asarray(traces[0].z, dtype=float))), 400)

    def _with_budget(self, budget, density_threshold=50000, **kw):
        TraceCreator.configure_view(max_points_sent=budget, density_threshold=density_threshold)
        return self.creator.create_cluster_traces(make_data(n=4000), **kw)

    def test_margin_shrinks_to_fit_budget(self):
        # 4000 clusters over 4x4 deg (250/deg2). View 1x1 deg: ~250 in view,
        # ~2250 with 100% margin, ~560 with 25%.
        view = (51.5, 52.5, -28.5, -27.5)
        wide = self._with_budget(5000, view_bounds=view)
        self.assertEqual({t.meta["cull_margin"] for t in wide}, {1.0})
        narrow = self._with_budget(1000, view_bounds=view)
        self.assertEqual({t.meta["cull_margin"] for t in narrow}, {0.25})
        self.assertTrue(all(not t.meta["density"] for t in narrow))
        self.assertTrue(all(t.type != "heatmap" for t in narrow))

    def test_density_only_when_view_over_threshold(self):
        view = (51.5, 52.5, -28.5, -27.5)  # ~250 clusters in view
        traces = self._with_budget(50000, density_threshold=100, view_bounds=view)
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].type, "heatmap")
        self.assertTrue(traces[0].meta["density"])
        # The browser estimates when to ask for markers from these two
        self.assertGreater(traces[0].meta["view_count"], 100)
        self.assertEqual(traces[0].meta["density_threshold"], 100)
        # Under the threshold: markers even when no margin fits the budget
        traces = self._with_budget(100, density_threshold=1000, view_bounds=view)
        self.assertTrue(all(t.type != "heatmap" for t in traces))
        self.assertEqual({t.meta["cull_margin"] for t in traces}, {0.0})

    def test_cull_settings(self):
        from cluster_visualization.callbacks.main_plot import MainPlotCallbacks

        cb = MainPlotCallbacks.__new__(MainPlotCallbacks)
        cb.trace_creator = self.creator
        small, big = make_data(n=100), make_data(n=6000)
        store = {"view": [50, 51, -29, -28], "sent": [50, 51, -29, -28]}
        self.assertEqual(cb._cull_settings(small, store), (None, False))
        self.assertEqual(cb._cull_settings(big, store), ((50.0, 51.0, -29.0, -28.0), True))
        self.assertEqual(cb._cull_settings(big, None), (None, True))
        TraceCreator.configure_view(cull_min_clusters=10000)
        self.assertEqual(cb._cull_settings(big, store), (None, False))

    def test_viewport_ack_ids(self):
        from cluster_visualization.callbacks.main_plot import MainPlotCallbacks

        # A viewport-triggered patch acks its request number; Apply / Re-render runs ack
        # with no id, so they never end a pending viewport request in the browser
        ack = MainPlotCallbacks._viewport_ack("viewport-request", 12)
        self.assertEqual(ack["id"], 12)
        self.assertIsNone(MainPlotCallbacks._viewport_ack("apply-filters-button", 12)["id"])
        self.assertIsNone(MainPlotCallbacks._viewport_ack("render-patch-request", 12)["id"])
        # A timestamp makes every ack a new value, so the browser tracker always fires
        self.assertIsInstance(ack["t"], float)

    def test_view_settings_from_config(self):
        import os
        import tempfile
        from cluster_visualization.src.config import Config

        with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False) as f:
            f.write("[view]\nmax_points_sent = 40000\ndensity_threshold = abc\n")
        try:
            cfg = Config.__new__(Config)
            import configparser
            cfg.config_parser = configparser.ConfigParser()
            cfg.config_parser.read(f.name)
            self.assertEqual(cfg.get_view_settings(),
                             {"cull_min_clusters": 5000, "max_points_sent": 40000, "density_threshold": 50000})
        finally:
            os.unlink(f.name)

    def test_customdata_is_numeric_binary(self):
        import plotly.graph_objects as go

        traces = self.creator.create_cluster_traces(make_data(n=200))
        merged = [t for t in traces if t.name and t.name.startswith("Merged")]
        self.assertTrue(merged)
        cd = np.asarray(merged[0].customdata)
        self.assertEqual(cd.shape[1], 5)
        self.assertEqual(cd.dtype, np.float32)  # test IDs are small, so float32 is exact
        np.testing.assert_array_equal(cd[:, 3].astype(np.int64) % 1, 0)
        # Sent through a Figure (as both the full render and the Apply patch do),
        # positions and customdata travel as typed binary
        data = go.Figure(data=merged).to_dict()["data"][0]
        for key in ("x", "y", "customdata"):
            self.assertIsInstance(data[key], dict, key)
            self.assertIn("bdata", data[key])


class TestCompactTraceData(unittest.TestCase):
    def test_large_ids_keep_float64(self):
        arr = np.zeros(2, dtype=MERGED_DTYPE)
        arr["ID_UNIQUE_CLUSTER"] = [2**24 + 1, 5]
        cd = TraceCreator._cluster_customdata(arr, [2, 2], [1, 1])
        self.assertEqual(cd.dtype, np.float64)
        self.assertEqual(int(cd[0, 3]), 2**24 + 1)

    def test_line_colors_palette(self):
        spec = TraceCreator._line_colors(["red", "blue", "red", "green"])
        self.assertEqual(spec["color"].dtype, np.uint8)
        palette = [c for _, c in spec["colorscale"]]
        self.assertEqual([palette[i] for i in spec["color"]], ["red", "blue", "red", "green"])
        self.assertEqual(TraceCreator._line_colors(["red", "red"])["color"], "red")
        self.assertEqual(TraceCreator._line_colors("black")["color"], "black")


class TestClickGate(unittest.TestCase):
    """Only cluster traces may open the cluster card (see handle_cluster_click)."""

    def test_cluster_traces_only(self):
        from cluster_visualization.src.visualization.trace_registry import TraceRegistry, TraceType

        def kind(name):
            return TraceRegistry.classify_trace({"name": name})

        for name in ("Merged PZWAV", "Unmerged AMICO", "PZWAV (Merged, near CATRED) - 3 clusters"):
            self.assertEqual(kind(name), TraceType.CLUSTER, name)
        for name in ("CATRED Masked - MER Tile", "Members (ID 5)", "Matched Pair", "Tile 3 CORE", "Mosaic x"):
            self.assertNotEqual(kind(name), TraceType.CLUSTER, name)


class TestPolygonMerge(unittest.TestCase):
    def test_same_style_tiles_share_a_trace(self):
        import plotly.graph_objects as go
        from cluster_visualization.src.visualization.trace_registry import TraceRegistry, TraceType

        square = ([0, 1, 1, 0, 0], [0, 0, 1, 1, 0])
        traces = []
        for tile, colour in [(1, "red"), (2, "blue"), (3, "red")]:
            traces.append(go.Scatter(x=square[0], y=square[1], mode="lines",
                                     line=dict(width=4, color=colour, dash="dash"),
                                     name=f"Tile {tile} LEV1", text=f"Tile {tile} - LEV1 Polygon"))
            traces.append(go.Scatter(x=square[0], y=square[1], mode="lines",
                                     line=dict(width=4, color=colour),
                                     name=f"Tile {tile} CORE", text=f"Tile {tile} - CORE Polygon"))
        merged = TraceCreator._merge_polygon_traces(traces)
        self.assertEqual(len(merged), 4)  # red/blue x LEV1/CORE
        self.assertTrue(all("CORE" in t.name for t in merged[:2]))  # fills under dashed lines
        red_lev1 = next(t for t in merged if "LEV1" in t.name and t.line.color == "red")
        self.assertEqual(len(red_lev1.x), 2 * 6)
        self.assertEqual(red_lev1.text[0], "Tile 1 - LEV1 Polygon")
        self.assertEqual(red_lev1.text[6], "Tile 3 - LEV1 Polygon")
        for trace in merged:  # still recognised as polygons by name
            self.assertEqual(TraceRegistry.classify_trace(trace), TraceType.POLYGON)


if __name__ == "__main__":
    unittest.main()
