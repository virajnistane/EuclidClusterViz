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


if __name__ == "__main__":
    unittest.main()
