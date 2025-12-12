"""
Tests for trace creation functionality.

Tests the TraceCreator class for various trace generation scenarios,
including cluster traces, MER traces, and polygon traces.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cluster_visualization"))

try:
    import plotly.graph_objs as go
    from visualization.traces import TraceCreator

    TRACE_CREATOR_AVAILABLE = True
except ImportError:
    TRACE_CREATOR_AVAILABLE = False

from tests import create_test_data


class TestTraceCreator(unittest.TestCase):
    """Test cases for TraceCreator class"""

    def setUp(self):
        """Set up test fixtures"""
        if not TRACE_CREATOR_AVAILABLE:
            self.skipTest("TraceCreator not available")

        # Mock color lists
        self.colors_list = ["red", "blue", "green", "orange", "purple"]
        self.colors_list_transparent = [
            "rgba(255,0,0,0.3)",
            "rgba(0,0,255,0.3)",
            "rgba(0,255,0,0.3)",
            "rgba(255,165,0,0.3)",
            "rgba(128,0,128,0.3)",
        ]

        # Mock MER handler
        self.mer_handler = MagicMock()

        self.trace_creator = TraceCreator(
            self.colors_list, self.colors_list_transparent, self.mer_handler
        )
        self.test_data = create_test_data()

    def test_trace_creator_initialization(self):
        """Test TraceCreator initialization"""
        self.assertIsNotNone(self.trace_creator)
        self.assertEqual(self.trace_creator.colors_list, self.colors_list)
        self.assertEqual(self.trace_creator.colors_list_transparent, self.colors_list_transparent)
        self.assertEqual(self.trace_creator.mer_handler, self.mer_handler)

    def test_create_cluster_traces_merged(self):
        """Test creating cluster traces for merged data"""
        traces = self.trace_creator._create_cluster_traces_merged(
            self.test_data["merged_data"], show_polygons=False
        )

        self.assertIsInstance(traces, list)
        self.assertGreater(len(traces), 0)

        # Check that traces are Scattergl objects
        for trace in traces:
            self.assertIsInstance(trace, go.Scattergl)

    def test_create_cluster_traces_merged_with_polygons(self):
        """Test creating cluster traces with polygons"""
        traces = self.trace_creator._create_cluster_traces_merged(
            self.test_data["merged_data"], show_polygons=True
        )

        self.assertIsInstance(traces, list)
        self.assertGreater(len(traces), 0)

        # When polygons are enabled, should include both scatter and polygon traces
        scatter_traces = [t for t in traces if isinstance(t, go.Scattergl)]
        polygon_traces = [t for t in traces if isinstance(t, go.Scatter)]

        self.assertGreater(len(scatter_traces), 0)
        # Note: Polygon traces depend on actual polygon data availability

    def test_create_cluster_traces_tiles(self):
        """Test creating cluster traces for tile data"""
        traces = self.trace_creator._create_cluster_traces_tiles(self.test_data["tile_data"])

        self.assertIsInstance(traces, list)
        self.assertGreater(len(traces), 0)

        # Check that traces are Scattergl objects
        for trace in traces:
            self.assertIsInstance(trace, go.Scattergl)

    def test_create_mer_traces(self):
        """Test creating MER traces"""
        # Mock MER data
        mer_data = {
            "trace_1": {
                "ra": [12.1, 12.2, 12.3],
                "dec": [-0.1, 0.0, 0.1],
                "phz_pdf": [np.array([0.1, 0.2]), np.array([0.2, 0.3]), np.array([0.3, 0.1])],
                "phz_mode_1": [0.5, 0.6, 0.4],
            }
        }

        traces = self.trace_creator._create_mer_traces(mer_data)

        self.assertIsInstance(traces, list)
        self.assertGreater(len(traces), 0)

        # Check that traces are Scattergl objects
        for trace in traces:
            self.assertIsInstance(trace, go.Scattergl)
            # MER traces should have custom data for click handling
            self.assertIsNotNone(trace.customdata)

    def test_filter_data_by_snr(self):
        """Test SNR filtering functionality"""
        # Test with lower bound only
        filtered = self.trace_creator._filter_data_by_snr(
            self.test_data["merged_data"], snr_threshold_lower=5.0
        )

        self.assertTrue(all(filtered["SNR_CLUSTER"] >= 5.0))

        # Test with upper bound only
        filtered = self.trace_creator._filter_data_by_snr(
            self.test_data["merged_data"], snr_threshold_upper=10.0
        )

        self.assertTrue(all(filtered["SNR_CLUSTER"] <= 10.0))

        # Test with both bounds
        filtered = self.trace_creator._filter_data_by_snr(
            self.test_data["merged_data"], snr_threshold_lower=5.0, snr_threshold_upper=10.0
        )

        self.assertTrue(all((filtered["SNR_CLUSTER"] >= 5.0) & (filtered["SNR_CLUSTER"] <= 10.0)))

    def test_filter_data_by_snr_no_filters(self):
        """Test SNR filtering with no filters applied"""
        original_data = self.test_data["merged_data"]
        filtered = self.trace_creator._filter_data_by_snr(original_data)

        # Should return original data unchanged
        pd.testing.assert_frame_equal(filtered, original_data)

    def test_create_all_traces_basic(self):
        """Test creating all traces with basic options"""
        traces = self.trace_creator.create_all_traces(
            self.test_data,
            show_polygons=False,
            show_mer_tiles=False,
            relayout_data=None,
            show_catred_mertile_data=False,
        )

        self.assertIsInstance(traces, list)
        self.assertGreater(len(traces), 0)

        # Should include both merged and tile traces
        trace_names = [trace.name for trace in traces if hasattr(trace, "name")]
        self.assertTrue(any("Merged" in name for name in trace_names))

    def test_create_all_traces_with_mer(self):
        """Test creating all traces with MER data"""
        # Mock MER handler to return data
        mock_mer_data = {
            "trace_1": {
                "ra": [12.1, 12.2],
                "dec": [-0.1, 0.0],
                "phz_pdf": [np.array([0.1, 0.2]), np.array([0.2, 0.3])],
                "phz_mode_1": [0.5, 0.6],
            }
        }

        traces = self.trace_creator.create_all_traces(
            self.test_data,
            show_polygons=False,
            show_mer_tiles=True,
            relayout_data=None,
            show_catred_mertile_data=True,
            manual_mer_data=mock_mer_data,
        )

        self.assertIsInstance(traces, list)
        self.assertGreater(len(traces), 0)

        # Should include MER traces
        trace_names = [trace.name for trace in traces if hasattr(trace, "name")]
        self.assertTrue(any("MER" in name for name in trace_names))

    def test_create_all_traces_with_existing_mer(self):
        """Test creating all traces with existing MER traces"""
        # Create mock existing MER trace
        existing_trace = go.Scattergl(
            x=[12.1, 12.2],
            y=[-0.1, 0.0],
            mode="markers",
            name="Existing MER Data",
            marker=dict(size=4, color="cyan"),
        )

        traces = self.trace_creator.create_all_traces(
            self.test_data,
            show_polygons=False,
            show_mer_tiles=True,
            relayout_data=None,
            show_catred_mertile_data=False,
            existing_mer_traces=[existing_trace],
        )

        self.assertIsInstance(traces, list)
        self.assertGreater(len(traces), 0)

        # Should include the existing MER trace
        trace_names = [trace.name for trace in traces if hasattr(trace, "name")]
        self.assertIn("Existing MER Data", trace_names)

    def test_create_all_traces_with_snr_filter(self):
        """Test creating all traces with SNR filtering"""
        traces = self.trace_creator.create_all_traces(
            self.test_data,
            show_polygons=False,
            show_mer_tiles=False,
            relayout_data=None,
            show_catred_mertile_data=False,
            snr_threshold_lower=5.0,
            snr_threshold_upper=10.0,
        )

        self.assertIsInstance(traces, list)

        # Verify that SNR filtering was applied
        # (This would require checking the actual data points in the traces)
        # For now, just verify traces were created
        self.assertGreater(len(traces), 0)

    def test_get_color_for_snr(self):
        """Test color selection based on SNR values"""
        # Test with various SNR values
        color1 = self.trace_creator._get_color_for_snr(3.0)
        color2 = self.trace_creator._get_color_for_snr(8.0)
        color3 = self.trace_creator._get_color_for_snr(15.0)

        # Should return valid colors
        self.assertIsNotNone(color1)
        self.assertIsNotNone(color2)
        self.assertIsNotNone(color3)

        # Colors should be from the color list
        self.assertIn(color1, self.colors_list)
        self.assertIn(color2, self.colors_list)
        self.assertIn(color3, self.colors_list)

    def test_format_hover_text(self):
        """Test hover text formatting"""
        # Create sample row data
        row_data = pd.Series(
            {"RA": 12.345, "DEC": -0.123, "SNR_CLUSTER": 7.89, "Z_CL": 0.456, "NOBJ": 25}
        )

        hover_text = self.trace_creator._format_hover_text(row_data)

        self.assertIsInstance(hover_text, str)
        self.assertIn("RA:", hover_text)
        self.assertIn("DEC:", hover_text)
        self.assertIn("SNR:", hover_text)
        self.assertIn("Z_CL:", hover_text)

        # Verify formatting precision
        self.assertIn("12.345", hover_text)
        self.assertIn("-0.123", hover_text)


class TestTraceCreatorEdgeCases(unittest.TestCase):
    """Test edge cases and error handling for TraceCreator"""

    def setUp(self):
        """Set up test fixtures"""
        if not TRACE_CREATOR_AVAILABLE:
            self.skipTest("TraceCreator not available")

        # Minimal setup for edge case testing
        self.colors_list = ["red", "blue"]
        self.colors_list_transparent = ["rgba(255,0,0,0.3)", "rgba(0,0,255,0.3)"]
        self.mer_handler = MagicMock()

        self.trace_creator = TraceCreator(
            self.colors_list, self.colors_list_transparent, self.mer_handler
        )

    def test_empty_data_handling(self):
        """Test handling of empty data"""
        empty_data = {
            "merged_data": pd.DataFrame(columns=["RA", "DEC", "SNR_CLUSTER"]),
            "tile_data": pd.DataFrame(columns=["RA", "DEC", "SNR_CLUSTER"]),
            "snr_min": 0,
            "snr_max": 100,
        }

        traces = self.trace_creator.create_all_traces(
            empty_data,
            show_polygons=False,
            show_mer_tiles=False,
            relayout_data=None,
            show_catred_mertile_data=False,
        )

        # Should handle empty data gracefully
        self.assertIsInstance(traces, list)

    def test_invalid_snr_bounds(self):
        """Test handling of invalid SNR bounds"""
        test_data = create_test_data()

        # Test with lower bound higher than upper bound
        filtered = self.trace_creator._filter_data_by_snr(
            test_data["merged_data"], snr_threshold_lower=10.0, snr_threshold_upper=5.0
        )

        # Should return empty dataframe or handle gracefully
        self.assertIsInstance(filtered, pd.DataFrame)

    def test_missing_columns(self):
        """Test handling of missing required columns"""
        # Create data with missing columns
        incomplete_data = pd.DataFrame(
            {
                "RA": [12.1, 12.2],
                "DEC": [-0.1, 0.0]
                # Missing SNR_CLUSTER column
            }
        )

        # Should handle missing columns gracefully
        try:
            traces = self.trace_creator._create_cluster_traces_merged(
                incomplete_data, show_polygons=False
            )
            self.assertIsInstance(traces, list)
        except Exception as e:
            # If it raises an exception, it should be a meaningful one
            self.assertIsInstance(e, (KeyError, ValueError))


if __name__ == "__main__":
    unittest.main()
