"""
MER (Multi-Epoch Reconstruction) data handling module.

This module handles loading and processing of MER tile data including:
- Individual MER tile FITS data loading
- Spatial intersection calculations with zoom windows
- PHZ (Photometric Redshift) data processing
- Fallback to polygon vertices when FITS data is unavailable
"""

import os
import pandas as pd
import numpy as np
from astropy.io import fits
from shapely.geometry import box
from typing import Dict, List, Any, Optional, Tuple


class MERHandler:
    """Handles MER tile data loading and spatial operations."""
    
    def __init__(self):
        """Initialize MER handler."""
        self.traces_cache = []  # Store accumulated MER scatter traces
        self.current_mer_data = None  # Store current MER data for click callbacks
    
    def get_radec_mertile(self, mertileid: int, data: Dict[str, Any]) -> Dict[str, List]:
        """
        Load CATRED data for a specific MER tile.
        
        Args:
            mertileid: The MER tile ID
            data: The data dictionary containing catred_info
            
        Returns:
            Dictionary with keys 'RIGHT_ASCENSION', 'DECLINATION', 'PHZ_MODE_1', 
            'PHZ_70_INT', 'PHZ_PDF' or empty dict {} if unable to load
        """
        try:
            if isinstance(mertileid, str):
                mertileid = int(mertileid)
            
            # Check if we have the necessary data
            if 'catred_info' not in data or data['catred_info'].empty:
                print(f"Debug: No catred_info available for mertile {mertileid}")
                return {}
            
            if mertileid not in data['catred_info'].index:
                print(f"Debug: MerTile {mertileid} not found in catred_info")
                return {}
            
            mertile_row = data['catred_info'].loc[mertileid]
            
            # Check if fits_file column exists
            if 'fits_file' not in mertile_row or pd.isna(mertile_row['fits_file']):
                print(f"Debug: No fits_file for mertile {mertileid}, using polygon vertices as demo data")
                return self._get_polygon_fallback_data(mertile_row, mertileid)
            
            # Try to load actual FITS file
            fits_path = mertile_row['fits_file']
            if not os.path.exists(fits_path):
                print(f"Debug: FITS file not found at {fits_path}, using polygon vertices")
                return self._get_polygon_fallback_data(mertile_row, mertileid)
            
            # Load actual FITS data
            return self._load_fits_data(fits_path)
                
        except Exception as e:
            print(f"Debug: Error loading MER tile {mertileid}: {e}")
            # Fallback: try to use polygon vertices
            try:
                if mertileid in data['catred_info'].index:
                    mertile_row = data['catred_info'].loc[mertileid]
                    return self._get_polygon_fallback_data(mertile_row, mertileid)
            except Exception as fallback_error:
                print(f"Debug: Fallback also failed for MER tile {mertileid}: {fallback_error}")
            
            return {}
    
    def _get_polygon_fallback_data(self, mertile_row: pd.Series, mertileid: int) -> Dict[str, List]:
        """Get fallback data using polygon vertices when FITS data is unavailable."""
        if 'polygon' in mertile_row and mertile_row['polygon'] is not None:
            poly = mertile_row['polygon']
            x_coords, y_coords = poly.exterior.xy
            num_points = len(x_coords)
            
            print(f"Debug: Using polygon vertices for MER tile {mertileid} ({num_points} points)")
            
            return {
                'RIGHT_ASCENSION': list(x_coords),
                'DECLINATION': list(y_coords),
                'PHZ_MODE_1': [0.0] * num_points,  # Dummy scalar values
                'PHZ_70_INT': [[0.0, 0.0]] * num_points,  # Dummy interval pairs
                'PHZ_PDF': [[0.0] * 10] * num_points  # Dummy PDF vectors
            }
        else:
            return {}
    
    def _load_fits_data(self, fits_path: str) -> Dict[str, List]:
        """Load MER data from FITS file."""
        with fits.open(fits_path) as hdul:
            fits_data = hdul[1].data
            
            # Extract the required columns
            result = {
                'RIGHT_ASCENSION': fits_data['RIGHT_ASCENSION'].tolist(),
                'DECLINATION': fits_data['DECLINATION'].tolist()
            }
            
            # Add photometric redshift columns if they exist
            for col in ['PHZ_MODE_1', 'PHZ_70_INT', 'PHZ_PDF']:
                if col in fits_data.columns.names:
                    col_data = fits_data[col]
                    result[col] = self._process_column_data(col, col_data)
                else:
                    # Provide dummy values if column doesn't exist
                    print(f"Debug: Column {col} not found in {fits_path}, using dummy values")
                    result[col] = self._get_dummy_column_data(col, len(result['RIGHT_ASCENSION']))
            
            return result
    
    def _process_column_data(self, col_name: str, col_data: np.ndarray) -> List:
        """Process column data based on column type."""
        if col_name == 'PHZ_PDF':
            # Keep PHZ_PDF as raw vectors - don't process
            return [row.tolist() if hasattr(row, 'tolist') else row for row in col_data]
        elif col_name == 'PHZ_70_INT':
            # For PHZ_70_INT, store the raw vectors for difference calculation
            if col_data.ndim > 1:
                return [row.tolist() if hasattr(row, 'tolist') else row for row in col_data]
            else:
                # If it's scalar, convert to list format for consistency
                return [[float(val), float(val)] for val in col_data]
        else:
            # For PHZ_MODE_1 and other scalar columns
            if col_data.ndim > 1:
                # Take first element if it's a vector
                return [float(row[0]) if len(row) > 0 else 0.0 for row in col_data]
            else:
                # Scalar column
                return col_data.tolist()
    
    def _get_dummy_column_data(self, col_name: str, num_points: int) -> List:
        """Generate dummy data for missing columns."""
        if col_name == 'PHZ_PDF':
            return [[0.0] * 10] * num_points  # Dummy vector
        elif col_name == 'PHZ_70_INT':
            return [[0.0, 0.0]] * num_points  # Dummy interval
        else:
            return [0.0] * num_points
    
    def load_mer_scatter_data(self, data: Dict[str, Any], relayout_data: Optional[Dict]) -> Dict[str, List]:
        """
        Load MER scatter data for the current zoom window.
        
        Args:
            data: The main data dictionary
            relayout_data: Current zoom/pan state from Plotly
            
        Returns:
            Dictionary with keys 'ra', 'dec', 'phz_mode_1', 'phz_70_int', 'phz_pdf'
        """
        mer_scatter_data = {
            'ra': [],
            'dec': [],
            'phz_mode_1': [],
            'phz_70_int': [],
            'phz_pdf': []
        }

        if not self._validate_catred_data(data):
            return mer_scatter_data
        
        if not relayout_data:
            print("Debug: No relayout data available for MER scatter")
            return mer_scatter_data
        
        # Extract zoom ranges from relayout data
        zoom_ranges = self._extract_zoom_ranges(relayout_data)
        if not zoom_ranges:
            return mer_scatter_data
        
        ra_min, ra_max, dec_min, dec_max = zoom_ranges
        print(f"Debug: Loading MER data for zoom box - RA: [{ra_min}, {ra_max}], Dec: [{dec_min}, {dec_max}]")

        # Find MER tiles that intersect with current zoom window
        mertiles_to_load = self._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)
        
        # Load data for each intersecting MER tile
        self._load_tile_data(mertiles_to_load, data, mer_scatter_data)
        
        print(f"Debug: Total MER scatter points loaded: {len(mer_scatter_data['ra'])}")
        return mer_scatter_data
    
    def _validate_catred_data(self, data: Dict[str, Any]) -> bool:
        """Validate that required CATRED data is available."""
        if 'catred_info' not in data or data['catred_info'].empty or 'polygon' not in data['catred_info'].columns:
            print("Debug: No catred_info data available for MER scatter")
            return False
        return True
    
    def _extract_zoom_ranges(self, relayout_data: Dict) -> Optional[Tuple[float, float, float, float]]:
        """Extract zoom ranges from Plotly relayout data."""
        ra_min = ra_max = dec_min = dec_max = None
        
        # Extract RA range
        if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
            ra_min = relayout_data['xaxis.range[0]']
            ra_max = relayout_data['xaxis.range[1]']
        elif 'xaxis.range' in relayout_data:
            ra_min = relayout_data['xaxis.range'][0]
            ra_max = relayout_data['xaxis.range'][1]

        # Extract Dec range
        if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
            dec_min = relayout_data['yaxis.range[0]']
            dec_max = relayout_data['yaxis.range[1]']
        elif 'yaxis.range' in relayout_data:
            dec_min = relayout_data['yaxis.range'][0]
            dec_max = relayout_data['yaxis.range'][1]
        
        if all(val is not None for val in [ra_min, ra_max, dec_min, dec_max]):
            return ra_min, ra_max, dec_min, dec_max
        return None
    
    def _find_intersecting_tiles(self, data: Dict[str, Any], ra_min: float, ra_max: float, 
                                dec_min: float, dec_max: float) -> List[int]:
        """Find MER tiles whose polygons intersect with the zoom box."""
        zoom_box = box(ra_min, dec_min, ra_max, dec_max)
        mertiles_to_load = []
        
        for mertileid, row in data['catred_info'].iterrows():
            poly = row['polygon']
            if poly is not None:
                # Use proper geometric intersection: checks if polygons overlap in any way
                # This handles cases where zoom box is inside polygon, polygon is inside zoom box,
                # or they partially overlap
                if poly.intersects(zoom_box):
                    mertiles_to_load.append(mertileid)

        print(f"Debug: Found {len(mertiles_to_load)} MER tiles in zoom area: "
              f"{mertiles_to_load[:5]}{'...' if len(mertiles_to_load) > 5 else ''}")
        
        return mertiles_to_load
    
    def _load_tile_data(self, mertiles_to_load: List[int], data: Dict[str, Any], 
                       mer_scatter_data: Dict[str, List]) -> None:
        """Load data for each MER tile and accumulate in scatter data."""
        for mertileid in mertiles_to_load:
            tile_data = self.get_radec_mertile(mertileid, data)
            if tile_data and 'RIGHT_ASCENSION' in tile_data:
                mer_scatter_data['ra'].extend(tile_data['RIGHT_ASCENSION'])
                mer_scatter_data['dec'].extend(tile_data['DECLINATION'])
                mer_scatter_data['phz_mode_1'].extend(tile_data['PHZ_MODE_1'])
                mer_scatter_data['phz_70_int'].extend(tile_data['PHZ_70_INT'])
                mer_scatter_data['phz_pdf'].extend(tile_data['PHZ_PDF'])
                print(f"Debug: Added {len(tile_data['RIGHT_ASCENSION'])} points from MER tile {mertileid}")
    
    def clear_traces_cache(self) -> None:
        """Clear the MER traces cache."""
        self.traces_cache = []
        print("MER traces cache cleared")
    
    def get_traces_count(self) -> int:
        """Get the number of cached MER traces."""
        return len(self.traces_cache)
