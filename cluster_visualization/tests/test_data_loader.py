"""
Tests for data loading and caching functionality.

Tests the DataLoader class for various data loading scenarios,
caching behavior, and error handling.
"""

import unittest
import tempfile
import os
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
import sys

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cluster_visualization'))

try:
    from data.loader import DataLoader
    DATA_LOADER_AVAILABLE = True
except ImportError:
    DATA_LOADER_AVAILABLE = False

from tests import create_test_data, create_test_config


class TestDataLoader(unittest.TestCase):
    """Test cases for DataLoader class"""
    
    def setUp(self):
        """Set up test fixtures"""
        if not DATA_LOADER_AVAILABLE:
            self.skipTest("DataLoader not available")
            
        self.test_config = create_test_config()
        self.test_data = create_test_data()
        self.loader = DataLoader(self.test_config, use_config=True)
    
    def test_data_loader_initialization(self):
        """Test DataLoader initialization"""
        self.assertIsNotNone(self.loader)
        self.assertEqual(self.loader.config, self.test_config)
        self.assertTrue(self.loader.use_config)
        self.assertEqual(self.loader.data_cache, {})
    
    def test_load_data_caching(self):
        """Test data loading with caching"""
        with patch.object(self.loader, '_load_data_from_files') as mock_load:
            mock_load.return_value = self.test_data
            
            # First call should load from files
            result1 = self.loader.load_data('PZWAV')
            self.assertEqual(result1, self.test_data)
            mock_load.assert_called_once_with('PZWAV')
            
            # Second call should use cache
            mock_load.reset_mock()
            result2 = self.loader.load_data('PZWAV')
            self.assertEqual(result2, self.test_data)
            mock_load.assert_not_called()
    
    def test_load_data_different_algorithms(self):
        """Test loading data for different algorithms"""
        with patch.object(self.loader, '_load_data_from_files') as mock_load:
            mock_load.return_value = self.test_data
            
            # Load PZWAV data
            result1 = self.loader.load_data('PZWAV')
            self.assertEqual(result1, self.test_data)
            
            # Load AMICO data (should be separate cache entry)
            result2 = self.loader.load_data('AMICO')
            self.assertEqual(result2, self.test_data)
            
            # Should have been called twice
            self.assertEqual(mock_load.call_count, 2)
    
    def test_snr_calculations(self):
        """Test SNR min/max calculations"""
        data = self.test_data.copy()
        
        # Test with sample data
        snr_min, snr_max = self.loader._calculate_snr_range(data['merged_data'])
        
        self.assertLessEqual(snr_min, snr_max)
        self.assertEqual(snr_min, data['merged_data']['SNR_CLUSTER'].min())
        self.assertEqual(snr_max, data['merged_data']['SNR_CLUSTER'].max())
    
    def test_snr_calculations_empty_data(self):
        """Test SNR calculations with empty data"""
        empty_data = pd.DataFrame(columns=['SNR_CLUSTER'])
        
        snr_min, snr_max = self.loader._calculate_snr_range(empty_data)
        
        # Should return default values
        self.assertEqual(snr_min, 0.0)
        self.assertEqual(snr_max, 100.0)
    
    @patch('pandas.read_csv')
    def test_load_data_from_files_success(self, mock_read_csv):
        """Test successful file loading"""
        # Mock file loading
        mock_read_csv.side_effect = [
            self.test_data['merged_data'],  # merged file
            self.test_data['tile_data']     # tile file
        ]
        
        result = self.loader._load_data_from_files('PZWAV')
        
        self.assertIn('merged_data', result)
        self.assertIn('tile_data', result)
        self.assertIn('snr_min', result)
        self.assertIn('snr_max', result)
        
        # Verify file reading was called
        self.assertEqual(mock_read_csv.call_count, 2)
    
    @patch('pandas.read_csv')
    def test_load_data_from_files_error(self, mock_read_csv):
        """Test file loading with errors"""
        # Mock file loading error
        mock_read_csv.side_effect = FileNotFoundError("File not found")
        
        with self.assertRaises(Exception):
            self.loader._load_data_from_files('INVALID')
    
    def test_get_algorithm_file_paths(self):
        """Test algorithm file path generation"""
        merged_path, tile_path = self.loader._get_algorithm_file_paths('PZWAV')
        
        self.assertIn('PZWAV', merged_path)
        self.assertIn('PZWAV', tile_path)
        self.assertTrue(merged_path.endswith('.csv'))
        self.assertTrue(tile_path.endswith('.csv'))
    
    def test_clear_cache(self):
        """Test cache clearing functionality"""
        # Add some data to cache
        self.loader.data_cache['PZWAV'] = self.test_data
        self.loader.data_cache['AMICO'] = self.test_data
        
        # Clear cache
        self.loader.clear_cache()
        
        self.assertEqual(len(self.loader.data_cache), 0)
    
    def test_fallback_without_config(self):
        """Test fallback behavior when config is not available"""
        fallback_loader = DataLoader(None, use_config=False)
        
        self.assertIsNone(fallback_loader.config)
        self.assertFalse(fallback_loader.use_config)
        
        # Should still initialize cache
        self.assertEqual(fallback_loader.data_cache, {})


class TestDataLoaderIntegration(unittest.TestCase):
    """Integration tests for DataLoader with real file operations"""
    
    def setUp(self):
        """Set up test fixtures with temporary files"""
        if not DATA_LOADER_AVAILABLE:
            self.skipTest("DataLoader not available")
            
        self.temp_dir = tempfile.mkdtemp()
        self.test_config = create_test_config()
        self.test_config.data_dir = self.temp_dir
        
        # Create test CSV files
        self.test_data = create_test_data()
        self._create_test_files()
        
        self.loader = DataLoader(self.test_config, use_config=True)
    
    def tearDown(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_test_files(self):
        """Create test CSV files"""
        # Create merged data file
        merged_path = os.path.join(self.temp_dir, 'PZWAV_merged.csv')
        self.test_data['merged_data'].to_csv(merged_path, index=False)
        
        # Create tile data file
        tile_path = os.path.join(self.temp_dir, 'PZWAV_tile.csv')
        self.test_data['tile_data'].to_csv(tile_path, index=False)
    
    def test_real_file_loading(self):
        """Test loading data from real files"""
        result = self.loader.load_data('PZWAV')
        
        self.assertIn('merged_data', result)
        self.assertIn('tile_data', result)
        self.assertIn('snr_min', result)
        self.assertIn('snr_max', result)
        
        # Verify data integrity
        self.assertEqual(len(result['merged_data']), len(self.test_data['merged_data']))
        self.assertEqual(len(result['tile_data']), len(self.test_data['tile_data']))


if __name__ == '__main__':
    unittest.main()
