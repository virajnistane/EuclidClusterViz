"""
"Include clusters with missing redshift / SNR" switches are disabled when every
loaded cluster has a value. MainPlotCallbacks._has_missing_values decides that from
the merged catalog (per algorithm via DET_CODE_NB) and the per-tile catalogs.
"""

import unittest

import numpy as np

from cluster_visualization.callbacks.main_plot import MainPlotCallbacks
from cluster_visualization.tests.test_incremental_render import make_data

has_missing = MainPlotCallbacks._has_missing_values


def complete_data():
    """Synthetic catalog with no missing redshift or SNR anywhere."""
    data = make_data()
    data["data_detcluster_mergedcat"]["Z_CLUSTER"] = np.linspace(0.1, 2.0, len(data["data_detcluster_mergedcat"]))
    return data


class TestMissingValueSwitches(unittest.TestCase):
    def test_nothing_missing(self):
        data = complete_data()
        self.assertFalse(has_missing(data, "Z_CLUSTER"))
        self.assertFalse(has_missing(data, "SNR_CLUSTER", det_code=2, tile_algorithm="PZWAV"))

    def test_missing_redshift_in_merged_catalog(self):
        data = complete_data()
        data["data_detcluster_mergedcat"]["Z_CLUSTER"][5] = np.nan
        self.assertTrue(has_missing(data, "Z_CLUSTER"))

    def test_det_code_subset_respected(self):
        data = complete_data()
        merged = data["data_detcluster_mergedcat"]
        amico_row = int(np.where(merged["DET_CODE_NB"] == 1)[0][0])
        merged["SNR_CLUSTER"][amico_row] = np.nan
        self.assertTrue(has_missing(data, "SNR_CLUSTER", det_code=1, tile_algorithm="AMICO"))
        self.assertFalse(has_missing(data, "SNR_CLUSTER", det_code=2, tile_algorithm="PZWAV"))

    def test_missing_only_in_tile_catalog(self):
        data = complete_data()
        tile = data["data_detcluster_by_cltile"]["1"]  # a PZWAV tile
        tile["detfits_data"] = np.zeros(
            3, dtype=[("RIGHT_ASCENSION_CLUSTER", "f8"), ("DECLINATION_CLUSTER", "f8"), ("SNR_CLUSTER", "f8")]
        )
        tile["detfits_data"]["SNR_CLUSTER"] = [5.0, np.nan, 7.0]
        self.assertTrue(has_missing(data, "SNR_CLUSTER", det_code=2, tile_algorithm="PZWAV"))
        self.assertFalse(has_missing(data, "SNR_CLUSTER", det_code=1, tile_algorithm="AMICO"))

    def test_absent_column_counts_as_nothing_missing(self):
        self.assertFalse(has_missing(complete_data(), "NOT_A_COLUMN"))

    def test_switch_state_label(self):
        callbacks = MainPlotCallbacks.__new__(MainPlotCallbacks)
        disabled, label = callbacks._missing_switch_state(complete_data(), "Z_CLUSTER", "redshift")
        self.assertTrue(disabled)
        self.assertEqual(label, "Include clusters with missing redshift (none missing)")
        data = complete_data()
        data["data_detcluster_mergedcat"]["Z_CLUSTER"][0] = np.nan
        disabled, label = callbacks._missing_switch_state(data, "Z_CLUSTER", "redshift")
        self.assertFalse(disabled)
        self.assertEqual(label, "Include clusters with missing redshift")


if __name__ == "__main__":
    unittest.main()
