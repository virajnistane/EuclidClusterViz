"""
Tests for figure management functionality.

Tests the FigureManager class for figure creation, layout management,
aspect ratio handling, and zoom state preservation.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    import plotly.graph_objs as go
    from visualization.figures import FigureManager

    FIGURE_MANAGER_AVAILABLE = True
except ImportError:
    FIGURE_MANAGER_AVAILABLE = False


class TestFigureManager(unittest.TestCase):
    """Test cases for FigureManager class"""

    def setUp(self):
        """Set up test fixtures"""
        if not FIGURE_MANAGER_AVAILABLE:
            self.skipTest("FigureManager not available")

        self.figure_manager = FigureManager()

    def test_figure_manager_initialization(self):
        """Test FigureManager initialization"""
        self.assertIsNotNone(self.figure_manager)

    def test_create_figure_basic(self):
        """Test basic figure creation"""
        # Create sample traces
        traces = [
            go.Scattergl(x=[12.1, 12.2, 12.3], y=[-0.1, 0.0, 0.1], mode="markers", name="Test Data")
        ]

        fig = self.figure_manager.create_figure(traces, "PZWAV", free_aspect_ratio=True)

        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 1)
        self.assertIn("PZWAV", fig.layout.title.text)

    def test_create_figure_free_aspect_ratio(self):
        """Test figure creation with free aspect ratio"""
        traces = [go.Scattergl(x=[12.1], y=[-0.1], mode="markers")]

        fig = self.figure_manager.create_figure(traces, "AMICO", free_aspect_ratio=True)

        # Free aspect ratio should not have scaleanchor
        self.assertNotEqual(fig.layout.xaxis.scaleanchor, "y")

    def test_create_figure_equal_aspect_ratio(self):
        """Test figure creation with equal aspect ratio"""
        traces = [go.Scattergl(x=[12.1], y=[-0.1], mode="markers")]

        fig = self.figure_manager.create_figure(traces, "AMICO", free_aspect_ratio=False)

        # Equal aspect ratio should have scaleanchor
        self.assertEqual(fig.layout.xaxis.scaleanchor, "y")
        self.assertEqual(fig.layout.xaxis.scaleratio, 1)

    def test_configure_axes_free_aspect(self):
        """Test axis configuration for free aspect ratio"""
        xaxis_config, yaxis_config = self.figure_manager._get_axis_config(free_aspect_ratio=True)

        self.assertIsInstance(xaxis_config, dict)
        self.assertIsInstance(yaxis_config, dict)
        self.assertTrue(xaxis_config.get("visible", False))
        self.assertTrue(yaxis_config.get("visible", False))
        self.assertNotIn("scaleanchor", xaxis_config)

    def test_configure_axes_equal_aspect(self):
        """Test axis configuration for equal aspect ratio"""
        xaxis_config, yaxis_config = self.figure_manager._get_axis_config(free_aspect_ratio=False)

        self.assertIsInstance(xaxis_config, dict)
        self.assertIsInstance(yaxis_config, dict)
        self.assertEqual(xaxis_config.get("scaleanchor"), "y")
        self.assertEqual(xaxis_config.get("scaleratio"), 1)
        self.assertEqual(xaxis_config.get("constrain"), "domain")
        self.assertEqual(yaxis_config.get("constrain"), "domain")

    def test_setup_layout_basic(self):
        """Test basic layout setup"""
        fig = go.Figure()

        self.figure_manager._setup_layout(fig, "Test Algorithm")

        self.assertIn("Test Algorithm", fig.layout.title.text)
        self.assertEqual(fig.layout.xaxis.title.text, "Right Ascension (degrees)")
        self.assertEqual(fig.layout.yaxis.title.text, "Declination (degrees)")
        self.assertEqual(fig.layout.hovermode, "closest")

    def test_setup_layout_legend(self):
        """Test legend configuration in layout"""
        fig = go.Figure()

        self.figure_manager._setup_layout(fig, "Test Algorithm")

        legend = fig.layout.legend
        self.assertEqual(legend.title.text, "Legend")
        self.assertEqual(legend.orientation, "v")
        self.assertEqual(legend.xanchor, "left")
        self.assertEqual(legend.x, 1.01)
        self.assertEqual(legend.yanchor, "top")
        self.assertEqual(legend.y, 1)

    def test_preserve_zoom_state_range_format(self):
        """Test zoom state preservation with range[0], range[1] format"""
        fig = go.Figure()

        relayout_data = {
            "xaxis.range[0]": 12.0,
            "xaxis.range[1]": 14.0,
            "yaxis.range[0]": -1.0,
            "yaxis.range[1]": 1.0,
        }

        self.figure_manager.preserve_zoom_state(fig, relayout_data)

        self.assertEqual(fig.layout.xaxis.range, (12.0, 14.0))
        self.assertEqual(fig.layout.yaxis.range, (-1.0, 1.0))

    def test_preserve_zoom_state_array_format(self):
        """Test zoom state preservation with range array format"""
        fig = go.Figure()

        relayout_data = {"xaxis.range": [12.5, 13.5], "yaxis.range": [-0.5, 0.5]}

        self.figure_manager.preserve_zoom_state(fig, relayout_data)

        self.assertEqual(fig.layout.xaxis.range, (12.5, 13.5))
        self.assertEqual(fig.layout.yaxis.range, (-0.5, 0.5))

    def test_preserve_zoom_state_current_figure_fallback(self):
        """Test zoom state preservation from current figure"""
        fig = go.Figure()

        current_figure = {
            "layout": {"xaxis": {"range": [11.0, 15.0]}, "yaxis": {"range": [-2.0, 2.0]}}
        }

        self.figure_manager.preserve_zoom_state(
            fig, relayout_data=None, current_figure=current_figure
        )

        self.assertEqual(fig.layout.xaxis.range, (11.0, 15.0))
        self.assertEqual(fig.layout.yaxis.range, (-2.0, 2.0))

    def test_preserve_zoom_state_no_data(self):
        """Test zoom state preservation with no data"""
        fig = go.Figure()
        original_xaxis_range = fig.layout.xaxis.range
        original_yaxis_range = fig.layout.yaxis.range

        self.figure_manager.preserve_zoom_state(fig, relayout_data=None, current_figure=None)

        # Should not modify the figure if no zoom data available
        self.assertEqual(fig.layout.xaxis.range, original_xaxis_range)
        self.assertEqual(fig.layout.yaxis.range, original_yaxis_range)

    def test_preserve_zoom_state_partial_data(self):
        """Test zoom state preservation with partial relayout data"""
        fig = go.Figure()

        # Only x-axis range provided
        relayout_data = {"xaxis.range[0]": 12.0, "xaxis.range[1]": 14.0}

        self.figure_manager.preserve_zoom_state(fig, relayout_data)

        # Should preserve x-axis range, y-axis should remain unchanged
        self.assertEqual(fig.layout.xaxis.range, (12.0, 14.0))
        # y-axis range should be None (unchanged)
        self.assertIsNone(fig.layout.yaxis.range)

    def test_create_figure_with_multiple_traces(self):
        """Test figure creation with multiple traces"""
        traces = [
            go.Scattergl(x=[12.1, 12.2], y=[-0.1, 0.0], mode="markers", name="Trace 1"),
            go.Scattergl(x=[12.3, 12.4], y=[0.1, 0.2], mode="markers", name="Trace 2"),
            go.Scatter(
                x=[12.1, 12.2, 12.3, 12.1], y=[-0.1, 0.0, 0.1, -0.1], mode="lines", name="Polygon"
            ),
        ]

        fig = self.figure_manager.create_figure(traces, "Multi-trace Test", free_aspect_ratio=True)

        self.assertEqual(len(fig.data), 3)
        self.assertEqual(fig.data[0].name, "Trace 1")
        self.assertEqual(fig.data[1].name, "Trace 2")
        self.assertEqual(fig.data[2].name, "Polygon")

    def test_layout_margins(self):
        """Test proper margin configuration"""
        fig = go.Figure()

        self.figure_manager._setup_layout(fig, "Test")

        margins = fig.layout.margin
        self.assertEqual(margins.l, 40)
        self.assertEqual(margins.r, 20)
        self.assertEqual(margins.t, 40)
        self.assertEqual(margins.b, 40)

    def test_autosize_configuration(self):
        """Test autosize configuration"""
        fig = go.Figure()

        self.figure_manager._setup_layout(fig, "Test")

        self.assertTrue(fig.layout.autosize)


class TestFigureManagerEdgeCases(unittest.TestCase):
    """Test edge cases and error handling for FigureManager"""

    def setUp(self):
        """Set up test fixtures"""
        if not FIGURE_MANAGER_AVAILABLE:
            self.skipTest("FigureManager not available")

        self.figure_manager = FigureManager()

    def test_empty_traces_list(self):
        """Test figure creation with empty traces list"""
        fig = self.figure_manager.create_figure([], "Empty Test", free_aspect_ratio=True)

        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 0)
        self.assertIn("Empty Test", fig.layout.title.text)

    def test_invalid_relayout_data(self):
        """Test zoom preservation with malformed relayout data"""
        fig = go.Figure()

        # Test with invalid data types
        invalid_relayout_data = {"xaxis.range[0]": "invalid", "yaxis.range[1]": None}

        # Should handle invalid data gracefully without crashing
        try:
            self.figure_manager.preserve_zoom_state(fig, invalid_relayout_data)
        except (TypeError, ValueError):
            # These exceptions are acceptable for invalid data
            pass

    def test_incomplete_current_figure_data(self):
        """Test zoom preservation with incomplete current figure data"""
        fig = go.Figure()

        # Incomplete current figure data
        incomplete_current_figure = {
            "layout": {
                "xaxis": {}  # Missing range
                # Missing yaxis entirely
            }
        }

        # Should handle incomplete data gracefully
        self.figure_manager.preserve_zoom_state(
            fig, relayout_data=None, current_figure=incomplete_current_figure
        )

        # Figure should remain unchanged
        self.assertIsNone(fig.layout.xaxis.range)
        self.assertIsNone(fig.layout.yaxis.range)


if __name__ == "__main__":
    unittest.main()
