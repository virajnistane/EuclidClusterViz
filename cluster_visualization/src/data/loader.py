"""
Data loading and caching module for cluster visualization.

This module handles all data loading operations including:
- Merged cluster detection catalogs
- Individual tile data
- CATRED file information and polygons
- SNR range calculations
- Data validation and caching
"""

import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from astropy.io import fits
from typing import Dict, Any, Optional


class DataLoader:
    """Handles loading and caching of cluster detection data."""
    
    def __init__(self, config=None, use_config=True):
        """
        Initialize DataLoader with configuration.
        
        Args:
            config: Configuration object with path information
            use_config: Whether to use configuration or fallback to hardcoded paths
        """
        self.config = config
        self.use_config = use_config
        self.data_cache = {}
        
        # Import utilities - handle import path resolution
        try:
            if use_config and config:
                utils_path = config.utils_dir
                if utils_path not in sys.path:
                    sys.path.append(utils_path)
            else:
                # Fallback: look for utilities in user's home directory
                utils_path = os.path.join(os.path.expanduser('~'), 'mypackage')
                if utils_path not in sys.path:
                    sys.path.append(utils_path)
            
            from myutils import get_xml_element
            self.get_xml_element = get_xml_element
            
        except ImportError as e:
            raise ImportError(f"Failed to import utilities: {e}")
    
    def load_data(self, select_algorithm: str = 'PZWAV') -> Dict[str, Any]:
        """
        Load and prepare all data for visualization.
        
        Args:
            select_algorithm: Algorithm choice ('PZWAV' or 'AMICO')
            
        Returns:
            Dict containing all loaded data:
            - merged_data: Merged cluster catalog
            - tile_data: Individual tile data by tile ID
            - catred_info: CATRED file information DataFrame
            - algorithm: Selected algorithm
            - snr_min/snr_max: SNR range for slider bounds
            - data_dir: Data directory path
            
        Raises:
            FileNotFoundError: If required data files are missing
            ValueError: If algorithm is not supported
        """
        # Check cache first
        if select_algorithm in self.data_cache:
            return self.data_cache[select_algorithm]
            
        print(f"Loading data for algorithm: {select_algorithm}")
        
        # Validate algorithm choice
        if select_algorithm not in ['PZWAV', 'AMICO']:
            print(f"Warning: Unknown algorithm '{select_algorithm}'. Using 'PZWAV' as default.")
            select_algorithm = 'PZWAV'
        
        # Get paths based on configuration
        paths = self._get_paths(select_algorithm)
        
        # Validate critical paths
        self._validate_paths(paths)
        
        # Load data components
        data_merged = self._load_merged_catalog(paths)
        data_by_tile = self._load_tile_data(paths)
        catred_fileinfo_df = self._load_catred_info(paths)
        
        # Calculate SNR range for UI slider
        snr_min = float(data_merged['SNR_CLUSTER'].min())
        snr_max = float(data_merged['SNR_CLUSTER'].max())
        print(f"SNR range: {snr_min:.3f} to {snr_max:.3f}")
        
        # Assemble final data structure
        data = {
            'merged_data': data_merged,
            'tile_data': data_by_tile,
            'catred_info': catred_fileinfo_df,
            'algorithm': select_algorithm,
            'snr_threshold_lower': None,  # Will be set by UI
            'snr_threshold_upper': None,  # Will be set by UI
            'snr_min': snr_min,
            'snr_max': snr_max,
            'data_dir': paths['data_dir']
        }
        
        # Cache the data for future requests
        self.data_cache[select_algorithm] = data
        return data
    
    def _get_paths(self, algorithm: str) -> Dict[str, str]:
        """Get file paths based on configuration or fallback."""
        if self.use_config and self.config:
            paths = {
                'mergedetcat_dir': self.config.mergedetcat_dir,
                'data_dir': self.config.mergedetcat_data_dir,
                'inputs_dir': self.config.mergedetcat_inputs_dir,
                'output_dir': self.config.get_output_dir(algorithm),
                'rr2_downloads_dir': self.config.rr2_downloads_dir,
                'catred_fileinfo_csv': self.config.get_catred_fileinfo_csv(),
                'catred_polygon_pkl': self.config.get_catred_polygons_pkl(),
                'detfiles_list': self.config.get_detfiles_list(algorithm)
            }
            print("✓ Using configuration-based paths")
        else:
            # Fallback to hardcoded paths
            base_dir = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir/MergeDetCat/RR2_south/'
            rr2_downloads = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir/RR2_downloads'
            
            paths = {
                'mergedetcat_dir': base_dir,
                'data_dir': os.path.join(base_dir, 'data'),
                'inputs_dir': os.path.join(base_dir, 'inputs'),
                'output_dir': os.path.join(base_dir, f'outvn_mergedetcat_rr2south_{algorithm}_3'),
                'rr2_downloads_dir': rr2_downloads,
                'catred_fileinfo_csv': os.path.join(rr2_downloads, 'catred_fileinfo.csv'),
                'catred_polygon_pkl': os.path.join(rr2_downloads, 'catred_polygons_by_tileid.pkl'),
                'detfiles_list': os.path.join(base_dir, f'detfiles_input_{algorithm.lower()}_3.json')
            }
            print("⚠️  Using fallback hardcoded paths")
        
        return paths
    
    def _validate_paths(self, paths: Dict[str, str]) -> None:
        """Validate that critical paths exist."""
        critical_paths = ['output_dir', 'data_dir']
        
        for path_key in critical_paths:
            path = paths[path_key]
            if not os.path.exists(path):
                raise FileNotFoundError(f"{path_key.replace('_', ' ').title()} not found: {path}")
    
    def _load_merged_catalog(self, paths: Dict[str, str]) -> np.ndarray:
        """Load merged detection catalog from XML and FITS files."""
        det_xml = os.path.join(paths['output_dir'], 'mergedetcat.xml')
        if not os.path.exists(det_xml):
            raise FileNotFoundError(f"Merged detection XML not found: {det_xml}")
        
        # Extract FITS filename from XML
        fits_filename = self.get_xml_element(det_xml, 'Data/ClustersFile/DataContainer/FileName').text
        fitsfile = os.path.join(paths['data_dir'], fits_filename)
        
        print(f"Loading merged catalog from: {os.path.basename(fitsfile)}")
        with fits.open(fitsfile) as hdul:
            data_merged = hdul[1].data
        
        print(f"Loaded {len(data_merged)} merged clusters")
        return data_merged
    
    def _load_tile_data(self, paths: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """Load individual tile detection data."""
        detfiles_list_path = paths['detfiles_list']
        if not os.path.exists(detfiles_list_path):
            raise FileNotFoundError(f"Detection files list not found: {detfiles_list_path}")
        
        with open(detfiles_list_path, 'r') as f:
            detfiles_list = json.load(f)
        
        data_by_tile = {}
        for file in detfiles_list:
            # Extract tile information from XML files
            xml_path = os.path.join(paths['inputs_dir'], file)
            tile_file = self.get_xml_element(xml_path, 'Data/SpatialInformation/DataContainer/FileName').text
            tile_id = tile_file.split('TILE_')[1][3:5]
            fits_file = self.get_xml_element(xml_path, 'Data/ClustersFile/DataContainer/FileName').text
            
            # Load FITS data for this tile
            fits_path = os.path.join(paths['data_dir'], fits_file)
            with fits.open(fits_path) as hdul:
                tile_data = hdul[1].data
            
            data_by_tile[tile_id] = {
                'tilefile': tile_file,
                'fitsfilename': fits_file,
                'data': tile_data
            }
        
        data_by_tile = dict(sorted(data_by_tile.items()))
        print(f"Loaded {len(data_by_tile)} individual tiles")
        return data_by_tile
    
    def _load_catred_info(self, paths: Dict[str, str]) -> pd.DataFrame:
        """Load CATRED file information and polygon data."""
        catred_fileinfo_csv = paths['catred_fileinfo_csv']
        catred_polygon_pkl = paths['catred_polygon_pkl']
        
        # Load CSV file info
        catred_fileinfo_df = pd.DataFrame()
        if os.path.exists(catred_fileinfo_csv):
            catred_fileinfo_df = pd.read_csv(catred_fileinfo_csv)
            catred_fileinfo_df.set_index('tileid', inplace=True)
            print("Loaded catred file info")
        else:
            print(f"Warning: catred_fileinfo.csv not found at {catred_fileinfo_csv}")
        
        # Load polygon data
        if os.path.exists(catred_polygon_pkl) and not catred_fileinfo_df.empty:
            with open(catred_polygon_pkl, 'rb') as f:
                catred_fileinfo_dict = pickle.load(f)
            catred_fileinfo_df['polygon'] = pd.Series(catred_fileinfo_dict)
            print("Loaded catred polygons")
        else:
            print(f"Warning: catred polygons not found at {catred_polygon_pkl}")
        
        return catred_fileinfo_df
    
    def clear_cache(self) -> None:
        """Clear the data cache to free memory."""
        self.data_cache.clear()
        print("Data cache cleared")
    
    def get_cached_algorithms(self) -> list:
        """Get list of currently cached algorithms."""
        return list(self.data_cache.keys())
