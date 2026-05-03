"""Focused tests for cluster tagging helper logic."""

import unittest

import numpy as np
import pandas as pd

from cluster_visualization.callbacks.cluster_modal_callbacks import ClusterModalCallbacks


class TestClusterTaggingHelpers(unittest.TestCase):
    """Test helper methods used by cluster tagging and CSV save workflow."""

    def setUp(self):
        self.callbacks = ClusterModalCallbacks.__new__(ClusterModalCallbacks)

    def _sample_catalog(self):
        dtype = [
            ("ID_UNIQUE_CLUSTER", np.int64),
            ("RIGHT_ASCENSION_CLUSTER", np.float64),
            ("DECLINATION_CLUSTER", np.float64),
            ("SNR_CLUSTER", np.float64),
            ("Z_CLUSTER", np.float64),
            ("DET_CODE_NB", np.int32),
        ]
        return np.array(
            [
                (101, 10.0000, -1.0000, 6.0, 0.30, 2),
                (102, 10.0020, -1.0020, 7.0, 0.40, 1),
            ],
            dtype=dtype,
        )

    def test_find_merged_record_by_cluster_id(self):
        catalog = self._sample_catalog()
        row = self.callbacks._find_merged_record_by_cluster_id(catalog, 101)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["ID_UNIQUE_CLUSTER"], 101)

    def test_match_merged_record_by_proximity_uses_tie_breakers(self):
        catalog = self._sample_catalog()
        row, distance_arcsec = self.callbacks._match_merged_record_by_proximity(
            catalog,
            ra=10.0018,
            dec=-1.0019,
            snr=7.1,
            redshift=0.41,
            det_code=1,
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["ID_UNIQUE_CLUSTER"], 102)
        self.assertGreaterEqual(distance_arcsec, 0.0)

    def test_reorder_tag_column_after_unique_id(self):
        df = pd.DataFrame(
            {
                "ID_UNIQUE_CLUSTER": [101],
                "RIGHT_ASCENSION_CLUSTER": [10.0],
                "cluster_tag": ["good"],
                "SNR_CLUSTER": [6.0],
            }
        )

        reordered = self.callbacks._reorder_tag_column(df)
        cols = list(reordered.columns)
        self.assertEqual(cols[0], "ID_UNIQUE_CLUSTER")
        self.assertEqual(cols[1], "cluster_tag")

    def test_merge_tagged_dataframes_replaces_existing_ids(self):
        existing = pd.DataFrame(
            {
                "ID_UNIQUE_CLUSTER": [101, 102],
                "cluster_tag": ["bad", "dubious"],
                "SNR_CLUSTER": [6.0, 7.0],
            }
        )
        incoming = pd.DataFrame(
            {
                "ID_UNIQUE_CLUSTER": [102, 103],
                "cluster_tag": ["good", "bad"],
                "SNR_CLUSTER": [8.0, 5.5],
            }
        )

        merged = self.callbacks._merge_tagged_dataframes(existing, incoming)

        # ID 102 should be replaced by incoming row, not duplicated.
        self.assertEqual(int((merged["ID_UNIQUE_CLUSTER"] == 102).sum()), 1)
        tag_102 = merged.loc[merged["ID_UNIQUE_CLUSTER"] == 102, "cluster_tag"].iloc[0]
        self.assertEqual(tag_102, "good")


if __name__ == "__main__":
    unittest.main()
