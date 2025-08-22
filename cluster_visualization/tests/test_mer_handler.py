"""
Tests for MER (Multi-Epoch Reconstruction) handler functionality.

Tests the MERHandler class for MER data loading, spatial calculations,
polygon operations, and PHZ data processing.
"""

import unittest
import tempfile
import os
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
import sys

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cluster_visualization'))

try:
    from data.mer_handler import MERHandler
    MER_HANDLER_AVAILABLE = True
except ImportError:
    MER_HANDLER_AVAILABLE = False

from tests import create_test_data


class TestMERHandler(unittest.TestCase):
    """Test cases for MERHandler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        if not MER_HANDLER_AVAILABLE:
            self.skipTest("MERHandler not available")
            
        self.handler = MERHandler()
        self.test_data = create_test_data()
    
    def test_mer_handler_initialization(self):
        """Test MERHandler initialization"""
        self.assertIsNotNone(self.handler)
        self.assertEqual(self.handler.traces_cache, [])
        self.assertIsNone(self.handler.current_mer_data)
    
    def test_clear_traces_cache(self):
        """Test clearing traces cache"""
        # Add some dummy traces
        self.handler.traces_cache = ['trace1', 'trace2', 'trace3']
        self.handler.current_mer_data = {'data': 'test'}
        
        self.handler.clear_traces_cache()
        
        self.assertEqual(self.handler.traces_cache, [])
        self.assertIsNone(self.handler.current_mer_data)
    
    def test_extract_zoom_ranges(self):
        """Test zoom range extraction from relayout data"""
        # Test with range format [0] and [1]
        relayout_data1 = {
            'xaxis.range[0]': 12.0,
            'xaxis.range[1]': 14.0,
            'yaxis.range[0]': -1.0,
            'yaxis.range[1]': 1.0
        }
        
        ra_bounds, dec_bounds = self.handler._extract_zoom_ranges(relayout_data1)
        
        self.assertEqual(ra_bounds, [12.0, 14.0])
        self.assertEqual(dec_bounds, [-1.0, 1.0])
        
        # Test with range format as array
        relayout_data2 = {
            'xaxis.range': [12.5, 13.5],
            'yaxis.range': [-0.5, 0.5]
        }
        
        ra_bounds, dec_bounds = self.handler._extract_zoom_ranges(relayout_data2)
        
        self.assertEqual(ra_bounds, [12.5, 13.5])
        self.assertEqual(dec_bounds, [-0.5, 0.5])
    
    def test_extract_zoom_ranges_no_data(self):
        """Test zoom range extraction with no relayout data"""
        ra_bounds, dec_bounds = self.handler._extract_zoom_ranges(None)
        
        self.assertIsNone(ra_bounds)
        self.assertIsNone(dec_bounds)
        
        # Test with empty dict
        ra_bounds, dec_bounds = self.handler._extract_zoom_ranges({})
        
        self.assertIsNone(ra_bounds)
        self.assertIsNone(dec_bounds)
    
    @patch('os.path.exists')
    def test_find_mer_tiles_in_region_success(self, mock_exists):
        """Test successful MER tile finding"""
        mock_exists.return_value = True
        
        with patch('os.listdir') as mock_listdir:
            mock_listdir.return_value = [
                'mer_tile_12_13_-1_0.fits',
                'mer_tile_13_14_0_1.fits',
                'other_file.txt'
            ]
            
            tiles = self.handler._find_mer_tiles_in_region([12.0, 14.0], [-1.0, 1.0])
            
            # Should find 2 matching tiles
            self.assertEqual(len(tiles), 2)
            self.assertIn('mer_tile_12_13_-1_0.fits', tiles)
            self.assertIn('mer_tile_13_14_0_1.fits', tiles)
    
    @patch('os.path.exists')
    def test_find_mer_tiles_in_region_no_dir(self, mock_exists):
        """Test MER tile finding when directory doesn't exist"""
        mock_exists.return_value = False
        
        tiles = self.handler._find_mer_tiles_in_region([12.0, 14.0], [-1.0, 1.0])
        
        self.assertEqual(tiles, [])
    
    def test_parse_tile_coordinates(self):
        """Test tile coordinate parsing from filename"""
        # Test valid filename
        ra_min, ra_max, dec_min, dec_max = self.handler._parse_tile_coordinates('mer_tile_12_13_-1_0.fits')
        
        self.assertEqual(ra_min, 12.0)
        self.assertEqual(ra_max, 13.0)
        self.assertEqual(dec_min, -1.0)
        self.assertEqual(dec_max, 0.0)
        
        # Test invalid filename
        result = self.handler._parse_tile_coordinates('invalid_filename.fits')
        self.assertIsNone(result)
    
    def test_tiles_intersect_region(self):
        """Test tile intersection with region"""
        # Test intersecting tile
        self.assertTrue(self.handler._tiles_intersect_region(
            12.0, 13.0, -1.0, 0.0,  # tile bounds
            [12.5, 14.0], [-0.5, 1.0]  # region bounds
        ))
        
        # Test non-intersecting tile
        self.assertFalse(self.handler._tiles_intersect_region(
            10.0, 11.0, -3.0, -2.0,  # tile bounds
            [12.5, 14.0], [-0.5, 1.0]  # region bounds
        ))
        
        # Test edge case - touching boundaries
        self.assertTrue(self.handler._tiles_intersect_region(
            12.0, 13.0, 0.0, 1.0,  # tile bounds
            [13.0, 14.0], [0.0, 1.0]  # region bounds (touching at edge)
        ))
    
    @patch('astropy.io.fits.open')
    def test_load_mer_data_from_tile_success(self, mock_fits_open):
        """Test successful MER data loading from tile"""
        # Mock FITS file structure
        mock_fits = MagicMock()
        mock_hdu = MagicMock()
        mock_data = MagicMock()
        
        # Mock the data structure
        mock_data.field.side_effect = lambda name: {
            'RIGHT_ASCENSION': np.array([12.1, 12.2, 12.3]),
            'DECLINATION': np.array([-0.1, 0.0, 0.1]),
            'PHZ_PDF': [np.array([0.1, 0.2, 0.3]), np.array([0.2, 0.3, 0.1]), np.array([0.3, 0.1, 0.2])],
            'PHZ_MODE_1': np.array([0.5, 0.6, 0.4])
        }[name]
        
        mock_hdu.data = mock_data
        mock_fits.__getitem__.return_value = mock_hdu
        mock_fits_open.return_value.__enter__.return_value = mock_fits
        
        result = self.handler._load_mer_data_from_tile('test_tile.fits', [12.0, 13.0], [-1.0, 1.0])
        
        self.assertIsNotNone(result)
        self.assertIn('ra', result)
        self.assertIn('dec', result)
        self.assertIn('phz_pdf', result)
        self.assertIn('phz_mode_1', result)
        
        # Verify data length
        self.assertEqual(len(result['ra']), 3)
        self.assertEqual(len(result['dec']), 3)
        self.assertEqual(len(result['phz_pdf']), 3)
        self.assertEqual(len(result['phz_mode_1']), 3)
    
    @patch('astropy.io.fits.open')
    def test_load_mer_data_from_tile_error(self, mock_fits_open):
        """Test MER data loading with file error"""
        mock_fits_open.side_effect = Exception("File read error")
        
        result = self.handler._load_mer_data_from_tile('bad_tile.fits', [12.0, 13.0], [-1.0, 1.0])
        
        self.assertIsNone(result)
    
    def test_filter_points_in_region(self):
        """Test point filtering within region"""
        # Create test points
        ra_coords = np.array([12.1, 12.5, 13.2, 11.5, 14.5])
        dec_coords = np.array([-0.1, 0.2, 0.8, -0.5, 1.2])
        phz_pdf = [np.array([0.1, 0.2]), np.array([0.2, 0.3]), np.array([0.3, 0.1]), 
                  np.array([0.1, 0.1]), np.array([0.2, 0.2])]
        phz_mode_1 = np.array([0.5, 0.6, 0.4, 0.3, 0.7])
        
        # Filter within region [12.0, 13.5] x [-0.5, 1.0]
        filtered = self.handler._filter_points_in_region(
            ra_coords, dec_coords, phz_pdf, phz_mode_1,
            [12.0, 13.5], [-0.5, 1.0]
        )
        
        # Should include points at indices 0, 1, 2, 3 (4 points)
        # Point at index 4 (14.5, 1.2) is outside the region
        self.assertEqual(len(filtered['ra']), 4)
        self.assertEqual(len(filtered['dec']), 4)
        self.assertEqual(len(filtered['phz_pdf']), 4)
        self.assertEqual(len(filtered['phz_mode_1']), 4)
    
    def test_combine_mer_data(self):
        """Test combining multiple MER data sets"""
        # Create test data sets
        data1 = {
            'ra': [12.1, 12.2],
            'dec': [-0.1, 0.0],
            'phz_pdf': [np.array([0.1, 0.2]), np.array([0.2, 0.3])],
            'phz_mode_1': [0.5, 0.6]
        }
        
        data2 = {
            'ra': [12.3, 12.4],
            'dec': [0.1, 0.2],
            'phz_pdf': [np.array([0.3, 0.1]), np.array([0.1, 0.3])],
            'phz_mode_1': [0.4, 0.7]
        }
        
        combined = self.handler._combine_mer_data([data1, data2])
        
        self.assertEqual(len(combined['ra']), 4)
        self.assertEqual(len(combined['dec']), 4)
        self.assertEqual(len(combined['phz_pdf']), 4)
        self.assertEqual(len(combined['phz_mode_1']), 4)
        
        # Verify order is preserved
        self.assertEqual(combined['ra'], [12.1, 12.2, 12.3, 12.4])
        self.assertEqual(combined['dec'], [-0.1, 0.0, 0.1, 0.2])
    
    def test_combine_mer_data_empty(self):
        """Test combining empty MER data sets"""
        combined = self.handler._combine_mer_data([])
        
        self.assertEqual(combined['ra'], [])
        self.assertEqual(combined['dec'], [])
        self.assertEqual(combined['phz_pdf'], [])
        self.assertEqual(combined['phz_mode_1'], [])
    
    @patch.object(MERHandler, '_find_mer_tiles_in_region')
    @patch.object(MERHandler, '_load_mer_data_from_tile')
    def test_load_mer_scatter_data_integration(self, mock_load_tile, mock_find_tiles):
        """Test full MER scatter data loading integration"""
        if not MER_HANDLER_AVAILABLE:
            self.skipTest("MERHandler not available")
            
        # Mock tile finding
        mock_find_tiles.return_value = ['tile1.fits', 'tile2.fits']
        
        # Mock tile data loading
        mock_load_tile.side_effect = [
            {
                'ra': [12.1, 12.2],
                'dec': [-0.1, 0.0],
                'phz_pdf': [np.array([0.1, 0.2]), np.array([0.2, 0.3])],
                'phz_mode_1': [0.5, 0.6]
            },
            {
                'ra': [12.3],
                'dec': [0.1],
                'phz_pdf': [np.array([0.3, 0.1])],
                'phz_mode_1': [0.4]
            }
        ]
        
        # Test relayout data
        relayout_data = {
            'xaxis.range[0]': 12.0,
            'xaxis.range[1]': 13.0,
            'yaxis.range[0]': -0.5,
            'yaxis.range[1]': 0.5
        }
        
        result = self.handler.load_mer_scatter_data(self.test_data, relayout_data)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result['ra']), 3)  # Combined from both tiles
        self.assertEqual(len(result['dec']), 3)
        self.assertEqual(len(result['phz_pdf']), 3)
        self.assertEqual(len(result['phz_mode_1']), 3)


if __name__ == '__main__':
    unittest.main()
