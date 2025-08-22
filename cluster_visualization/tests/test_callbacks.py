"""
Tests for callback modules.

Tests the callback classes for proper initialization, callback registration,
and interaction handling.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cluster_visualization'))

try:
    from src.callbacks.main_plot import MainPlotCallbacks
    from src.callbacks.mer_callbacks import MERCallbacks
    from src.callbacks.ui_callbacks import UICallbacks
    from src.callbacks.phz_callbacks import PHZCallbacks
    CALLBACKS_AVAILABLE = True
except ImportError:
    CALLBACKS_AVAILABLE = False

from tests import create_test_data


class TestMainPlotCallbacks(unittest.TestCase):
    """Test cases for MainPlotCallbacks class"""
    
    def setUp(self):
        """Set up test fixtures"""
        if not CALLBACKS_AVAILABLE:
            self.skipTest("Callbacks not available")
            
        self.mock_app = MagicMock()
        self.mock_data_loader = MagicMock()
        self.mock_mer_handler = MagicMock()
        self.mock_trace_creator = MagicMock()
        self.mock_figure_manager = MagicMock()
        
        self.test_data = create_test_data()
        
        # Mock data loader to return test data
        self.mock_data_loader.load_data.return_value = self.test_data
        
        self.main_plot_callbacks = MainPlotCallbacks(
            self.mock_app,
            self.mock_data_loader,
            self.mock_mer_handler,
            self.mock_trace_creator,
            self.mock_figure_manager
        )
    
    def test_main_plot_callbacks_initialization(self):
        """Test MainPlotCallbacks initialization"""
        self.assertIsNotNone(self.main_plot_callbacks)
        self.assertEqual(self.main_plot_callbacks.app, self.mock_app)
        self.assertEqual(self.main_plot_callbacks.data_loader, self.mock_data_loader)
        self.assertEqual(self.main_plot_callbacks.mer_handler, self.mock_mer_handler)
        self.assertEqual(self.main_plot_callbacks.trace_creator, self.mock_trace_creator)
        self.assertEqual(self.main_plot_callbacks.figure_manager, self.mock_figure_manager)
    
    def test_load_data_with_modular_loader(self):
        """Test data loading with modular data loader"""
        result = self.main_plot_callbacks.load_data('PZWAV')
        
        self.mock_data_loader.load_data.assert_called_once_with('PZWAV')
        self.assertEqual(result, self.test_data)
    
    def test_load_data_fallback(self):
        """Test data loading with fallback when no modular loader"""
        # Create callbacks without data loader
        fallback_callbacks = MainPlotCallbacks(
            self.mock_app, None, self.mock_mer_handler, 
            self.mock_trace_creator, self.mock_figure_manager
        )
        
        result = fallback_callbacks.load_data('PZWAV')
        
        # Should use fallback method and return default structure
        self.assertIn('merged_data', result)
        self.assertIn('tile_data', result)
        self.assertIn('snr_min', result)
        self.assertIn('snr_max', result)
    
    def test_create_traces_with_modular_creator(self):
        """Test trace creation with modular trace creator"""
        mock_traces = ['trace1', 'trace2']
        self.mock_trace_creator.create_all_traces.return_value = mock_traces
        
        result = self.main_plot_callbacks.create_traces(
            self.test_data, True, False, None, True
        )
        
        self.mock_trace_creator.create_all_traces.assert_called_once()
        self.assertEqual(result, mock_traces)
    
    def test_create_traces_fallback(self):
        """Test trace creation with fallback when no modular creator"""
        # Create callbacks without trace creator
        fallback_callbacks = MainPlotCallbacks(
            self.mock_app, self.mock_data_loader, self.mock_mer_handler, 
            None, self.mock_figure_manager
        )
        
        result = fallback_callbacks.create_traces(
            self.test_data, True, False, None, True
        )
        
        # Should use fallback method and return empty list
        self.assertEqual(result, [])
    
    def test_calculate_filtered_count(self):
        """Test SNR filtering count calculation"""
        # Test with no filters
        count = self.main_plot_callbacks._calculate_filtered_count(
            self.test_data['merged_data'], None, None
        )
        self.assertEqual(count, len(self.test_data['merged_data']))
        
        # Test with lower bound
        count = self.main_plot_callbacks._calculate_filtered_count(
            self.test_data['merged_data'], 5.0, None
        )
        expected = len(self.test_data['merged_data'][self.test_data['merged_data']['SNR_CLUSTER'] >= 5.0])
        self.assertEqual(count, expected)
        
        # Test with upper bound
        count = self.main_plot_callbacks._calculate_filtered_count(
            self.test_data['merged_data'], None, 10.0
        )
        expected = len(self.test_data['merged_data'][self.test_data['merged_data']['SNR_CLUSTER'] <= 10.0])
        self.assertEqual(count, expected)
        
        # Test with both bounds
        count = self.main_plot_callbacks._calculate_filtered_count(
            self.test_data['merged_data'], 5.0, 10.0
        )
        filtered_data = self.test_data['merged_data']
        expected = len(filtered_data[(filtered_data['SNR_CLUSTER'] >= 5.0) & (filtered_data['SNR_CLUSTER'] <= 10.0)])
        self.assertEqual(count, expected)
    
    def test_extract_existing_mer_traces(self):
        """Test extraction of existing MER traces from figure"""
        # Mock figure with MER traces
        current_figure = {
            'data': [
                {
                    'name': 'Regular Data',
                    'x': [1, 2, 3],
                    'y': [1, 2, 3]
                },
                {
                    'name': 'MER High-Res Data (Region 1)',
                    'x': [12.1, 12.2],
                    'y': [-0.1, 0.0],
                    'mode': 'markers',
                    'marker': {'size': 4}
                },
                {
                    'name': 'MER Tiles High-Res Data (Region 2)',
                    'x': [12.3, 12.4],
                    'y': [0.1, 0.2],
                    'mode': 'markers',
                    'marker': {'size': 4}
                }
            ]
        }
        
        existing_traces = self.main_plot_callbacks._extract_existing_mer_traces(current_figure)
        
        # Should extract 2 MER traces
        self.assertEqual(len(existing_traces), 2)
        
        # Verify trace names
        trace_names = [trace.name for trace in existing_traces]
        self.assertIn('MER High-Res Data (Region 1)', trace_names)
        self.assertIn('MER Tiles High-Res Data (Region 2)', trace_names)


class TestMERCallbacks(unittest.TestCase):
    """Test cases for MERCallbacks class"""
    
    def setUp(self):
        """Set up test fixtures"""
        if not CALLBACKS_AVAILABLE:
            self.skipTest("Callbacks not available")
            
        self.mock_app = MagicMock()
        self.mock_data_loader = MagicMock()
        self.mock_mer_handler = MagicMock()
        self.mock_trace_creator = MagicMock()
        self.mock_figure_manager = MagicMock()
        
        self.mer_callbacks = MERCallbacks(
            self.mock_app,
            self.mock_data_loader,
            self.mock_mer_handler,
            self.mock_trace_creator,
            self.mock_figure_manager
        )
    
    def test_mer_callbacks_initialization(self):
        """Test MERCallbacks initialization"""
        self.assertIsNotNone(self.mer_callbacks)
        self.assertEqual(self.mer_callbacks.app, self.mock_app)
        self.assertEqual(self.mer_callbacks.mer_handler, self.mock_mer_handler)
    
    def test_extract_zoom_ranges(self):
        """Test zoom range extraction"""
        # Test with range[0], range[1] format
        relayout_data = {
            'xaxis.range[0]': 12.0,
            'xaxis.range[1]': 14.0,
            'yaxis.range[0]': -1.0,
            'yaxis.range[1]': 1.0
        }
        
        ra_range, dec_range = self.mer_callbacks._extract_zoom_ranges(relayout_data)
        
        self.assertEqual(ra_range, 2.0)  # 14.0 - 12.0
        self.assertEqual(dec_range, 2.0)  # 1.0 - (-1.0)
        
        # Test with range array format
        relayout_data2 = {
            'xaxis.range': [12.5, 13.5],
            'yaxis.range': [-0.5, 0.5]
        }
        
        ra_range, dec_range = self.mer_callbacks._extract_zoom_ranges(relayout_data2)
        
        self.assertEqual(ra_range, 1.0)  # 13.5 - 12.5
        self.assertEqual(dec_range, 1.0)  # 0.5 - (-0.5)
    
    def test_load_mer_scatter_data_with_handler(self):
        """Test MER scatter data loading with handler"""
        mock_mer_data = {'ra': [12.1], 'dec': [-0.1]}
        self.mock_mer_handler.load_mer_scatter_data.return_value = mock_mer_data
        
        result = self.mer_callbacks.load_mer_scatter_data(create_test_data(), None)
        
        self.mock_mer_handler.load_mer_scatter_data.assert_called_once()
        self.assertEqual(result, mock_mer_data)
    
    def test_load_mer_scatter_data_fallback(self):
        """Test MER scatter data loading with fallback"""
        # Create callbacks without MER handler
        fallback_callbacks = MERCallbacks(
            self.mock_app, self.mock_data_loader, None, 
            self.mock_trace_creator, self.mock_figure_manager
        )
        
        result = fallback_callbacks.load_mer_scatter_data(create_test_data(), None)
        
        # Should use fallback method
        self.assertEqual(result, {'ra': [], 'dec': [], 'phz_pdf': [], 'phz_mode_1': []})


class TestUICallbacks(unittest.TestCase):
    """Test cases for UICallbacks class"""
    
    def setUp(self):
        """Set up test fixtures"""
        if not CALLBACKS_AVAILABLE:
            self.skipTest("Callbacks not available")
            
        self.mock_app = MagicMock()
        self.ui_callbacks = UICallbacks(self.mock_app)
    
    def test_ui_callbacks_initialization(self):
        """Test UICallbacks initialization"""
        self.assertIsNotNone(self.ui_callbacks)
        self.assertEqual(self.ui_callbacks.app, self.mock_app)


class TestPHZCallbacks(unittest.TestCase):
    """Test cases for PHZCallbacks class"""
    
    def setUp(self):
        """Set up test fixtures"""
        if not CALLBACKS_AVAILABLE:
            self.skipTest("Callbacks not available")
            
        self.mock_app = MagicMock()
        self.mock_mer_handler = MagicMock()
        
        self.phz_callbacks = PHZCallbacks(self.mock_app, self.mock_mer_handler)
    
    def test_phz_callbacks_initialization(self):
        """Test PHZCallbacks initialization"""
        self.assertIsNotNone(self.phz_callbacks)
        self.assertEqual(self.phz_callbacks.app, self.mock_app)
        self.assertEqual(self.phz_callbacks.mer_handler, self.mock_mer_handler)
    
    def test_phz_callbacks_fallback_initialization(self):
        """Test PHZCallbacks initialization without MER handler"""
        fallback_callbacks = PHZCallbacks(self.mock_app, None)
        
        self.assertIsNotNone(fallback_callbacks)
        self.assertIsNone(fallback_callbacks.mer_handler)
        self.assertIsNone(fallback_callbacks.current_mer_data)


if __name__ == '__main__':
    unittest.main()
