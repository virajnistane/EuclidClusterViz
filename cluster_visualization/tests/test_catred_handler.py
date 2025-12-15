"""
Tests for CATRED handler functionality.

Tests the CATREDHandler class for MER data loading, spatial calculations,
polygon operations, and PHZ data processing.
"""

import os
import sys
import tempfile
from typing import Dict, List
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cluster_visualization"))

try:
    from data.catred_handler import CATREDHandler

    CATRED_HANDLER_AVAILABLE = True
except ImportError:
    CATRED_HANDLER_AVAILABLE = False

from tests import create_test_data


class TestCATREDHandler(unittest.TestCase):
    """Test cases for CATREDHandler class"""

    def setUp(self):
        """Set up test fixtures"""
        if not CATRED_HANDLER_AVAILABLE:
            self.skipTest("CATREDHandler not available")

        self.handler = CATREDHandler()
        self.test_data = create_test_data()

    def test_catred_handler_initialization(self):
        """Test CATREDHandler initialization"""
        self.assertIsNotNone(self.handler)
        self.assertEqual(self.handler.traces_cache, [])
        self.assertIsNone(self.handler.current_catred_data)

    def test_clear_traces_cache(self):
        """Test clearing traces cache"""
        # Add some dummy traces
        self.handler.traces_cache = ["trace1", "trace2", "trace3"]
        self.handler.current_catred_data = {"data": "test"}

        # Clear cache
        self.handler.clear_traces_cache()

        # Verify cache is cleared but current_catred_data remains
        self.assertEqual(self.handler.traces_cache, [])
        self.assertIsNotNone(self.handler.current_catred_data)

    def test_get_traces_count(self):
        """Test getting traces count"""
        # Initially should be 0
        self.assertEqual(self.handler.get_traces_count(), 0)

        # Add some traces
        self.handler.traces_cache = ["trace1", "trace2"]
        self.assertEqual(self.handler.get_traces_count(), 2)

        # Add more traces
        self.handler.traces_cache.append("trace3")
        self.assertEqual(self.handler.get_traces_count(), 3)

    def test_get_radec_mertile_missing_data(self):
        """Test get_radec_mertile with missing data"""
        # Test with empty data
        result = self.handler.get_radec_mertile(1, {})
        self.assertEqual(result, {})

        # Test with no catred_info
        data = {"other_info": pd.DataFrame()}
        result = self.handler.get_radec_mertile(1, data)
        self.assertEqual(result, {})

        # Test with empty catred_info
        data = {"catred_info": pd.DataFrame()}
        result = self.handler.get_radec_mertile(1, data)
        self.assertEqual(result, {})

    def test_get_radec_mertile_invalid_id(self):
        """Test get_radec_mertile with invalid mertile ID"""
        data = self.test_data.copy()

        # Test with non-existent ID
        result = self.handler.get_radec_mertile(99999, data)
        self.assertEqual(result, {})

        # Test with string ID that converts to valid int
        if 1 in data["catred_info"].index:
            result = self.handler.get_radec_mertile("1", data)
            self.assertIsInstance(result, dict)

    def test_get_radec_mertile_polygon_fallback(self):
        """Test get_radec_mertile with polygon fallback"""
        data = self.test_data.copy()

        # Get a valid mertile ID
        if not data["catred_info"].empty:
            mertile_id = data["catred_info"].index[0]

            # Remove fits_file to force polygon fallback
            if "fits_file" in data["catred_info"].columns:
                data["catred_info"].loc[mertile_id, "fits_file"] = None

            result = self.handler.get_radec_mertile(mertile_id, data)

            # Should return polygon data if polygon exists
            if (
                "polygon" in data["catred_info"].columns
                and data["catred_info"].loc[mertile_id, "polygon"] is not None
            ):
                self.assertIsInstance(result, dict)
                if result:  # Only check if result is not empty
                    self.assertIn("RIGHT_ASCENSION", result)
                    self.assertIn("DECLINATION", result)
                    self.assertIn("PHZ_MODE_1", result)
                    self.assertIn("PHZ_70_INT", result)
                    self.assertIn("PHZ_PDF", result)

    def test_load_catred_scatter_data_no_relayout(self):
        """Test load_catred_scatter_data without relayout data"""
        data = self.test_data.copy()

        result = self.handler.load_catred_scatter_data(data, None)

        # Should return empty structure
        expected_keys = ["ra", "dec", "phz_mode_1", "phz_70_int", "phz_pdf"]
        self.assertIsInstance(result, dict)
        for key in expected_keys:
            self.assertIn(key, result)
            self.assertIsInstance(result[key], list)
            self.assertEqual(len(result[key]), 0)

    def test_load_catred_scatter_data_no_catred_info(self):
        """Test load_catred_scatter_data without catred_info"""
        data: dict = {}
        relayout_data = {"xaxis.range": [10.0, 11.0], "yaxis.range": [-5.0, -4.0]}

        result = self.handler.load_catred_scatter_data(data, relayout_data)

        # Should return empty structure
        expected_keys = ["ra", "dec", "phz_mode_1", "phz_70_int", "phz_pdf"]
        self.assertIsInstance(result, dict)
        for key in expected_keys:
            self.assertIn(key, result)
            self.assertIsInstance(result[key], list)
            self.assertEqual(len(result[key]), 0)

    def test_load_catred_scatter_data_with_zoom(self):
        """Test load_catred_scatter_data with zoom window"""
        data = self.test_data.copy()

        # Define a zoom window that should intersect with test data
        relayout_data = {"xaxis.range": [10.0, 11.0], "yaxis.range": [-5.0, -4.0]}

        result = self.handler.load_catred_scatter_data(data, relayout_data)

        # Should return valid structure even if no data intersects
        expected_keys = ["ra", "dec", "phz_mode_1", "phz_70_int", "phz_pdf"]
        self.assertIsInstance(result, dict)
        for key in expected_keys:
            self.assertIn(key, result)
            self.assertIsInstance(result[key], list)

    def test_validate_catred_data(self):
        """Test _validate_catred_data method"""
        # Test with valid data
        data = self.test_data.copy()
        if "catred_info" in data and "polygon" in data["catred_info"].columns:
            self.assertTrue(self.handler._validate_catred_data(data))

        # Test with no catred_info
        self.assertFalse(self.handler._validate_catred_data({}))

        # Test with empty catred_info
        data_empty = {"catred_info": pd.DataFrame()}
        self.assertFalse(self.handler._validate_catred_data(data_empty))

        # Test with catred_info missing polygon column
        data_no_polygon = {"catred_info": pd.DataFrame({"other_col": [1, 2, 3]})}
        self.assertFalse(self.handler._validate_catred_data(data_no_polygon))

    def test_extract_zoom_ranges(self):
        """Test _extract_zoom_ranges method"""
        # Test with complete range data
        relayout_data = {
            "xaxis.range[0]": 10.0,
            "xaxis.range[1]": 11.0,
            "yaxis.range[0]": -5.0,
            "yaxis.range[1]": -4.0,
        }
        result = self.handler._extract_zoom_ranges(relayout_data)
        self.assertEqual(result, (10.0, 11.0, -5.0, -4.0))

        # Test with list format
        relayout_data_list = {"xaxis.range": [10.0, 11.0], "yaxis.range": [-5.0, -4.0]}
        result = self.handler._extract_zoom_ranges(relayout_data_list)
        self.assertEqual(result, (10.0, 11.0, -5.0, -4.0))

        # Test with missing data
        incomplete_data = {"xaxis.range[0]": 10.0, "yaxis.range[0]": -5.0}
        result = self.handler._extract_zoom_ranges(incomplete_data)
        self.assertIsNone(result)

    def test_find_intersecting_tiles(self):
        """Test _find_intersecting_tiles method"""
        data = self.test_data.copy()

        if "catred_info" in data and not data["catred_info"].empty:
            # Test with a large zoom box that should include all tiles
            ra_min, ra_max = 0.0, 20.0
            dec_min, dec_max = -10.0, 10.0

            result = self.handler._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)
            self.assertIsInstance(result, list)

            # Test with a small zoom box that might not intersect
            ra_min, ra_max = 100.0, 101.0
            dec_min, dec_max = 100.0, 101.0

            result = self.handler._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)
            self.assertIsInstance(result, list)

    @patch("builtins.open")
    @patch("astropy.io.fits.open")
    def test_load_fits_data(self, mock_fits_open, mock_open):
        """Test _load_fits_data method"""
        # Mock FITS data
        mock_data = MagicMock()
        mock_data.columns.names = [
            "RIGHT_ASCENSION",
            "DECLINATION",
            "PHZ_MODE_1",
            "PHZ_70_INT",
            "PHZ_PDF",
        ]
        mock_data["RIGHT_ASCENSION"] = np.array([10.0, 10.1, 10.2])
        mock_data["DECLINATION"] = np.array([-5.0, -5.1, -5.2])
        mock_data["PHZ_MODE_1"] = np.array([0.5, 0.6, 0.7])
        mock_data["PHZ_70_INT"] = np.array([[0.4, 0.6], [0.5, 0.7], [0.6, 0.8]])
        mock_data["PHZ_PDF"] = np.array([[0.1] * 10, [0.2] * 10, [0.3] * 10])

        mock_hdul = MagicMock()
        mock_hdul[1].data = mock_data
        mock_fits_open.return_value.__enter__.return_value = mock_hdul

        result = self.handler._load_fits_data("dummy_path.fits")

        self.assertIsInstance(result, dict)
        self.assertIn("RIGHT_ASCENSION", result)
        self.assertIn("DECLINATION", result)
        self.assertIn("PHZ_MODE_1", result)
        self.assertIn("PHZ_70_INT", result)
        self.assertIn("PHZ_PDF", result)

        # Check data types and lengths
        self.assertEqual(len(result["RIGHT_ASCENSION"]), 3)
        self.assertEqual(len(result["DECLINATION"]), 3)
        self.assertEqual(len(result["PHZ_MODE_1"]), 3)

    def test_process_column_data(self):
        """Test _process_column_data method"""
        # Test PHZ_PDF processing (should keep as vectors)
        pdf_data = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        result = self.handler._process_column_data("PHZ_PDF", pdf_data)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], [0.1, 0.2, 0.3])

        # Test PHZ_70_INT processing
        int_data = np.array([[0.1, 0.2], [0.3, 0.4]])
        result = self.handler._process_column_data("PHZ_70_INT", int_data)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], [0.1, 0.2])

        # Test PHZ_MODE_1 processing (scalar)
        mode_data = np.array([0.5, 0.6, 0.7])
        result = self.handler._process_column_data("PHZ_MODE_1", mode_data)
        self.assertEqual(result, [0.5, 0.6, 0.7])

        # Test PHZ_MODE_1 with vector data (take first element)
        mode_vector_data = np.array([[0.5, 0.1], [0.6, 0.2], [0.7, 0.3]])
        result = self.handler._process_column_data("PHZ_MODE_1", mode_vector_data)
        self.assertEqual(result, [0.5, 0.6, 0.7])

    def test_get_dummy_column_data(self):
        """Test _get_dummy_column_data method"""
        # Test PHZ_PDF dummy data
        result = self.handler._get_dummy_column_data("PHZ_PDF", 3)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], [0.0] * 10)

        # Test PHZ_70_INT dummy data
        result = self.handler._get_dummy_column_data("PHZ_70_INT", 3)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], [0.0, 0.0])

        # Test PHZ_MODE_1 dummy data
        result = self.handler._get_dummy_column_data("PHZ_MODE_1", 3)
        self.assertEqual(result, [0.0, 0.0, 0.0])

    def test_load_tile_data(self):
        """Test _load_tile_data method"""
        data = self.test_data.copy()
        catred_scatter_data: Dict[str, List] = {
            "ra": [],
            "dec": [],
            "phz_mode_1": [],
            "phz_70_int": [],
            "phz_pdf": [],
        }

        if "catred_info" in data and not data["catred_info"].empty:
            mertiles_to_load = list(data["catred_info"].index[:2])  # Load first 2 tiles

            self.handler._load_tile_data(mertiles_to_load, data, catred_scatter_data)

            # Should maintain the structure even if no data is loaded
            for key in catred_scatter_data:
                self.assertIsInstance(catred_scatter_data[key], list)


if __name__ == "__main__":
    unittest.main()
