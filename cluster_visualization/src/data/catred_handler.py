"""
CATRED (MER Multi-Epoch Reconstruction) data handling module.

This module handles loading and processing of MER tile data including:
- Individual MER tile FITS data loading
- Spatial intersection calculations with zoom windows
- PHZ (Photometric Redshift) data processing
- Fallback to polygon vertices when FITS data is unavailable
"""

import os
import pandas as pd # type: ignore[import]
import numpy as np
from astropy.io import fits # type: ignore[import]
from astropy.table import Table # type: ignore[import]

try:
    import healpy as hp # type: ignore[import]
except ImportError:
    raise ImportError(
        "healpy is required for CATRED operations. Install with: pip install healpy"
    )

from shapely.geometry import box # type: ignore[import]
from typing import Dict, List, Any, Optional, Tuple


class Mask:
    """
    HEALPix mask class for effective coverage operations.
    
    This class handles loading and operations on effective coverage masks
    stored as HEALPix maps in FITS files.
    """
    
    def __init__(self, in_file: str):
        """
        Initialize mask from FITS file.
        
        Args:
            in_file: Path to the effective coverage mask FITS file
        """
        self.in_file = in_file
        self.read_msk()
    
    def read_msk(self):
        """Read the sparse HEALPix mask from FITS file."""
        with fits.open(self.in_file, mode='readonly') as hpfile:
            self.hdr = hpfile[1].header
            
            # Get NSIDE from header (sparse HEALPix format)
            self.nside = self.hdr['NSIDE']
            
            # Get the ordering scheme
            self.ordering = self.hdr.get('ORDERING', 'NESTED').upper()
            self.nested = (self.ordering == 'NESTED')
            
            # Read sparse data (PIXEL indices and WEIGHT values)
            pixel_indices = hpfile[1].data['PIXEL']
            weight_values = hpfile[1].data['WEIGHT']
            
            # Create full HEALPix map (filled with zeros, then populate sparse values)
            npix = 12 * self.nside**2
            self.hpdata = np.zeros(npix, dtype=np.float32)
            self.hpdata[pixel_indices] = weight_values
            
            print(f"Debug: Loaded sparse HEALPix mask: nside={self.nside}, ordering={self.ordering}, "
                  f"sparse_pixels={len(pixel_indices)}, total_pixels={npix}")
            
    def radec_to_hpcell(self, ra: np.ndarray, dec: np.ndarray) -> np.ndarray:
        """
        Convert RA/Dec coordinates to HEALPix cell indices.
        
        Args:
            ra: Right Ascension array in degrees
            dec: Declination array in degrees
            
        Returns:
            HEALPix cell indices
        """
        return hp.ang2pix(self.nside, ra, dec, lonlat=True, nest=self.nested)


def get_masked_catred(tile_id, effcovmask_info, effcovmask_dsr, catred_info, catred_dsr, maglim=24.0, threshold=0.8):
    """Get masked CATRED data for a tile using effective coverage mask and magnitude limit."""
    try:

        if effcovmask_dsr is None:
            raise ValueError("effcovmask_dsr must be provided to load effective coverage mask.")
        
        # Load mask for the tile
        mask_file = effcovmask_info.loc[(effcovmask_info['mertileid'] == tile_id) & (effcovmask_info['dataset_release'] == effcovmask_dsr)].squeeze()['fits_file']
        msk = Mask(mask_file)  # Pass file path to constructor
        
        # Load CATRED data
        catred_file = catred_info.loc[(catred_info['mertileid'] == tile_id) & (catred_info['dataset_release'] == catred_dsr)].squeeze()['fits_file']
        with fits.open(catred_file, mode='readonly', memmap=True) as catred_hdu:
            src = Table(catred_hdu[1].data)
            
        # Get HEALPix cells for each source (using proper column names)
        hp_cells = msk.radec_to_hpcell(src['RIGHT_ASCENSION'], src['DECLINATION'])
        
        # Get effective coverage for each source position
        eff_cov = msk.hpdata[hp_cells]
        
        if threshold == 1:
            threshold = 0.99  # Adjust threshold to avoid exact 1.0 filtering issues

        # Apply threshold filter
        coverage_mask = eff_cov >= threshold
        filtered_src = src[coverage_mask]
        
        # Apply magnitude limit filter if available
        if maglim is not None and maglim < 99.0:
            try:
                import sys
                import os
                cluster_viz_root = os.path.join(os.path.dirname(__file__), '..', '..')
                sys.path.insert(0, cluster_viz_root)
                
                from utils.magnitude import Magnitude
                magnitude_handler = Magnitude()
                filtered_src = magnitude_handler.apply_magnitude_cut(filtered_src, maglim=maglim)
                print(f"Debug: Applied magnitude limit {maglim} to tile {tile_id}")
            except (ImportError, Exception) as e:
                print(f"Warning: Magnitude filtering requested but not available: {e}")
        
        # Add columns to match expected format for plotting
        if 'RA' not in filtered_src.colnames:
            filtered_src['RA'] = filtered_src['RIGHT_ASCENSION']
        if 'DEC' not in filtered_src.colnames:
            filtered_src['DEC'] = filtered_src['DECLINATION']
        
        # Add effective coverage column for client-side filtering (for remaining sources)
        if len(filtered_src) > 0:
            # Recalculate effective coverage for the filtered sources
            filtered_hp_cells = msk.radec_to_hpcell(filtered_src['RIGHT_ASCENSION'], filtered_src['DECLINATION'])
            filtered_eff_cov = msk.hpdata[filtered_hp_cells]
            filtered_src['EFFECTIVE_COVERAGE'] = filtered_eff_cov
        else:
            filtered_src['EFFECTIVE_COVERAGE'] = []
            
        return filtered_src
        
    except Exception as e:
        print(f"Error in get_masked_catred: {e}")
        raise



class CATREDHandler:
    """Handles MER tile data loading and spatial operations."""
    
    def __init__(self):
        """Initialize CATRED handler."""
        self.traces_cache = []  # Store accumulated CATRED scatter traces
        self.current_catred_data = None  # Store current CATRED data for click callbacks
        self.catred_z_param_select_for_filter = 'PHZ_MEDIAN'  # Default redshift parameter for filtering
        self.catred_dsr = None  # Dataset release for CATRED files
        self.effcovmask_dsr = None  # Dataset release for effective coverage mask files
    
    def get_radec_mertile(self, mertileid: int, data: Dict[str, Any], maglim: float = 24.0) -> Dict[str, List]:
        """
        Load CATRED data for a specific MER tile.
        
        Args:
            mertileid: The MER tile ID
            data: The data dictionary containing catred_info
            maglim: Magnitude limit for filtering (default 24.0)
            
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
            
            if mertileid not in data['catred_info']['mertileid'].values:
                print(f"Debug: MerTile {mertileid} not found in catred_info")
                return {}

            if (data.get('catred_dsr', None) not in data['catred_info']['dataset_release'].values or 
                 data.get('effcovmask_dsr', None) not in data['effcovmask_info']['dataset_release'].values):
                print(f"Debug: catred_dsr {data.get('catred_dsr', None)} or effcovmask_dsr {data.get('effcovmask_dsr', None)} not found in catred_info or effcovmask_info for mertile {mertileid}")
                return {}
            
            mertile_row = data['catred_info'].loc[data['catred_info']['mertileid'] == mertileid &
                                                  data['catred_info']['dataset_release'] == data.get('catred_dsr', None)].squeeze()
            
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
            return self._load_fits_data(fits_path, maglim)
                
        except Exception as e:
            print(f"Debug: Error loading MER tile {mertileid}: {e}")
            # Fallback: try to use polygon vertices
            try:
                if mertileid in data['catred_info']['mertileid'].values:
                    mertile_row = data['catred_info'].loc[(data['catred_info']['mertileid'] == mertileid) & (data['catred_info']['dataset_release'] == data.get('catred_dsr', None))].squeeze()
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
                'PHZ_MEDIAN': [0.5] * num_points,  # Dummy median values
                'PHZ_70_INT': [[0.0, 0.0]] * num_points,  # Dummy interval pairs
                'PHZ_PDF': [[0.0] * 10] * num_points,  # Dummy PDF vectors
                'KRON_RADIUS': [0.0] * num_points  # Dummy Kron radius values
            }
        else:
            return {}
    
    def _load_fits_data(self, fits_path: str, maglim: float = 24.0) -> Dict[str, List]:
        """Load MER data from FITS file with magnitude filtering."""
        with fits.open(fits_path, mode='readonly', memmap=True) as hdul:
            fits_data = hdul[1].data
            
            # Apply magnitude filtering if available
            if maglim < 99.0:  # Only apply if a realistic magnitude limit is set
                try:
                    # Try to import magnitude module
                    import sys
                    import os
                    cluster_viz_root = os.path.join(os.path.dirname(__file__), '..', '..')
                    sys.path.insert(0, cluster_viz_root)
                    
                    from utils.magnitude import Magnitude
                    magnitude_handler = Magnitude()
                    
                    # Apply magnitude cut to the FITS data
                    fits_data = magnitude_handler.apply_magnitude_cut(fits_data, maglim)
                    print(f"Debug: Applied magnitude limit {maglim} to FITS data, {len(fits_data)} objects remaining")
                    
                except (ImportError, Exception) as e:
                    print(f"Debug: Magnitude filtering not available for {fits_path}: {e}")
            
            
            # Extract the required columns
            result = {
                'RIGHT_ASCENSION': fits_data['RIGHT_ASCENSION'].tolist(),
                'DECLINATION': fits_data['DECLINATION'].tolist()
            }
            
            # Add photometric redshift columns if they exist
            for col in ['PHZ_MODE_1', 'PHZ_70_INT', 'PHZ_PDF', 'PHZ_MEDIAN', 'KRON_RADIUS']:
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
            # For PHZ_MODE_1, PHZ_MEDIAN, KRON_RADIUS, and other scalar columns
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

    def _validate_catred_data(self, data: Dict[str, Any]) -> bool:
        """Validate that required CATRED data is available."""
        if 'catred_info' not in data or data['catred_info'].empty or 'polygon' not in data['catred_info'].columns:
            print("Debug: No catred_info data available for MER scatter")
            return False
        return True
    
    def _find_intersecting_tiles(
            self, data: Dict[str, Any], ra_min: float, ra_max: float, dec_min: float, dec_max: float
            ) -> List[int]:
        """Find MER tiles whose polygons intersect with the zoom box."""
        zoom_box = box(ra_min, dec_min, ra_max, dec_max)
        mertiles_to_load = []
        
        for uid, row in data['catred_info'].loc[data['catred_info']['dataset_release'] == data.get('catred_dsr', None)].iterrows():
            mertileid = row['mertileid']
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
    
    def get_radec_mertile_with_coverage(
            self, mertileid: int, data: Dict[str, Any], 
            maglim: float = None, threshold: float = 0.8, box: Dict[str, float] = None
            ) -> Dict[str, List]:
        """
        Load full CATRED data for a specific MER tile with effective coverage values for client-side filtering.
        
        Args:
            mertileid: The MER tile ID
            data: The data dictionary containing catred_info and effcovmask_info
            maglim: Magnitude limit for filtering (default: None for no magnitude filtering)
            
        Returns:
            Dictionary with keys 'RIGHT_ASCENSION', 'DECLINATION', 'PHZ_MODE_1', 'PHZ_MEDIAN',
            'PHZ_70_INT', 'PHZ_PDF', 'KRON_RADIUS', 'EFFECTIVE_COVERAGE' for all sources or empty dict {} if unable to load
        """
        try:
            if isinstance(mertileid, str):
                mertileid = int(mertileid)
            
            # Check if we have the necessary data
            if ('catred_info' not in data or data['catred_info'].empty or
                'effcovmask_info' not in data or data['effcovmask_info'].empty):
                print(f"Debug: Missing catred_info or effcovmask_info for coverage processing of mertile {mertileid}")
                return {}
            
            if (mertileid not in data['catred_info']['mertileid'].values or 
                mertileid not in data['effcovmask_info']['mertileid'].values):
                print(f"Debug: MerTile {mertileid} not found in catred_info or effcovmask_info")
                return {}
            
            if (data.get('catred_dsr', None) not in data['catred_info']['dataset_release'].values or 
                 data.get('effcovmask_dsr', None) not in data['effcovmask_info']['dataset_release'].values):
                print(f"Debug: catred_dsr {data.get('catred_dsr', None)} or effcovmask_dsr {data.get('effcovmask_dsr', None)} not found in catred_info or effcovmask_info for mertile {mertileid}")
                return {}
            
            # Get full CATRED data with coverage values (no threshold filtering)
            full_src_with_coverage = get_masked_catred(
                mertileid, data['effcovmask_info'], data.get('effcovmask_dsr', None), data['catred_info'], data.get('catred_dsr', None), maglim=maglim, threshold=threshold
                )  # Load all data
            
            if len(full_src_with_coverage) == 0:
                print(f"Debug: No CATRED sources found for mertile {mertileid}")
                return {}
            
            # Apply box selection if provided
            if box:
                full_src_with_coverage = self.apply_box_selection(full_src_with_coverage, box)

            # Convert to format expected by plotting functions, including effective coverage
            result = {
                'RIGHT_ASCENSION': full_src_with_coverage['RA'].tolist(),
                'DECLINATION': full_src_with_coverage['DEC'].tolist(),
                'PHZ_MODE_1': full_src_with_coverage['PHZ_MODE_1'].tolist() if 'PHZ_MODE_1' in full_src_with_coverage.colnames else [0.5] * len(full_src_with_coverage),
                'PHZ_MEDIAN': full_src_with_coverage['PHZ_MEDIAN'].tolist() if 'PHZ_MEDIAN' in full_src_with_coverage.colnames else [0.5] * len(full_src_with_coverage),
                'PHZ_70_INT': full_src_with_coverage['PHZ_70_INT'].tolist() if 'PHZ_70_INT' in full_src_with_coverage.colnames else [[0.1, 0.9]] * len(full_src_with_coverage),
                'PHZ_PDF': full_src_with_coverage['PHZ_PDF'].tolist() if 'PHZ_PDF' in full_src_with_coverage.colnames else [None] * len(full_src_with_coverage),
                'KRON_RADIUS': full_src_with_coverage['KRON_RADIUS'].tolist() if 'KRON_RADIUS' in full_src_with_coverage.colnames else [0.0] * len(full_src_with_coverage),
                'EFFECTIVE_COVERAGE': full_src_with_coverage['EFFECTIVE_COVERAGE'].tolist() if 'EFFECTIVE_COVERAGE' in full_src_with_coverage.colnames else [1.0] * len(full_src_with_coverage)
            }
            
            print(f"Debug: Loaded {len(result['RIGHT_ASCENSION'])} sources with coverage from MER tile {mertileid}")
            return result
            
        except Exception as e:
            print(f"Debug: Error loading CATRED data with coverage for mertile {mertileid}: {e}")
            return {}

    def get_radec_mertile_masked(self, mertileid: int, data: Dict[str, Any], 
                                threshold: float = 0.8, maglim: float = None, box: Optional[Dict[str, float]] = None) -> Dict[str, List]:
        """
        Load masked CATRED data for a specific MER tile based on effective coverage and magnitude limit.
        
        Args:
            mertileid: The MER tile ID
            data: The data dictionary containing catred_info and effcovmask_info
            threshold: Effective coverage threshold for filtering (default 0.8)
            maglim: Magnitude limit for filtering (default: None for no magnitude filtering)
            
        Returns:
            Dictionary with keys 'RIGHT_ASCENSION', 'DECLINATION', 'PHZ_MODE_1', 
            'PHZ_70_INT', 'PHZ_PDF' for sources above threshold or empty dict {} if unable to load
        """
        try:
            if isinstance(mertileid, str):
                mertileid = int(mertileid)
            
            # Check if we have the necessary data
            if ('catred_info' not in data or data['catred_info'].empty or
                'effcovmask_info' not in data or data['effcovmask_info'].empty):
                print(f"Debug: Missing catred_info or effcovmask_info for masked processing of mertile {mertileid}")
                return {}
            
            if (mertileid not in data['catred_info']['mertileid'].values or 
                mertileid not in data['effcovmask_info']['mertileid'].values):
                print(f"Debug: MerTile {mertileid} not found in catred_info or effcovmask_info")
                return {}

            if (data.get('catred_dsr', None) not in data['catred_info']['dataset_release'].values or 
                 data.get('effcovmask_dsr', None) not in data['effcovmask_info']['dataset_release'].values):
                print(f"Debug: catred_dsr {data.get('catred_dsr', None)} or effcovmask_dsr {data.get('effcovmask_dsr', None)} not found in catred_info or effcovmask_info for mertile {mertileid}")
                return {}
            
            # Get masked CATRED data
            filtered_src = get_masked_catred(mertileid, data['effcovmask_info'], data.get('effcovmask_dsr', None),
                                             data['catred_info'], data.get('catred_dsr', None), maglim=maglim, threshold=threshold)
            
            if len(filtered_src) == 0:
                print(f"Debug: No sources above threshold {threshold} for mertile {mertileid}")
                return {}

            # Apply box selection if provided
            if box:
                filtered_src = self.apply_box_selection(filtered_src, box)

            # Convert to format expected by plotting functions
            result = {
                'RIGHT_ASCENSION': filtered_src['RA'].tolist(),
                'DECLINATION': filtered_src['DEC'].tolist(),
                'PHZ_MODE_1': filtered_src['PHZ_MODE_1'].tolist() if 'PHZ_MODE_1' in filtered_src.colnames else [0.5] * len(filtered_src),
                'PHZ_MEDIAN': filtered_src['PHZ_MEDIAN'].tolist() if 'PHZ_MEDIAN' in filtered_src.colnames else [0.5] * len(filtered_src),
                'PHZ_70_INT': filtered_src['PHZ_70_INT'].tolist() if 'PHZ_70_INT' in filtered_src.colnames else [[0.1, 0.9]] * len(filtered_src),
                'PHZ_PDF': filtered_src['PHZ_PDF'].tolist() if 'PHZ_PDF' in filtered_src.colnames else [None] * len(filtered_src),
                'KRON_RADIUS': filtered_src['KRON_RADIUS'].tolist() if 'KRON_RADIUS' in filtered_src.colnames else [0.0] * len(filtered_src),
                'EFFECTIVE_COVERAGE': filtered_src['EFFECTIVE_COVERAGE'].tolist() if 'EFFECTIVE_COVERAGE' in filtered_src.colnames else [1.0] * len(filtered_src)
            }
            
            print(f"Debug: Loaded {len(result['RIGHT_ASCENSION'])} masked sources from MER tile {mertileid} (threshold={threshold})")
            return result
                
        except Exception as e:
            print(f"Debug: Error loading masked MER tile {mertileid}: {e}")
            return {}

    def update_catred_data_with_coverage(
            self, zoom_data: Dict[str, Any], data: Dict[str, Any], maglim: float = 24.0, threshold: float = 0.8
            ) -> Dict[str, List]:
        """
        Update CATRED data with effective coverage values for client-side threshold filtering.
        
        Args:
            zoom_data: Dictionary containing zoom window parameters
            data: Main data dictionary containing MER tile information
            maglim: Magnitude limit for filtering (default 24.0)
            
        Returns:
            Dictionary with scatter plot data including effective coverage values
        """
        catred_scatter_data = {
            'ra': [],
            'dec': [],
            'phz_mode_1': [],
            'phz_median': [],
            'phz_70_int': [],
            'phz_pdf': [],
            'kron_radius': [],
            'effective_coverage': []  # Add coverage data for client-side filtering
        }

        if 'catred_info' not in data or data['catred_info'].empty or 'polygon' not in data['catred_info'].columns:
            print("Debug: No catred_info data available for coverage-based CATRED loading")
            return catred_scatter_data

        # Find mertileids whose polygons intersect with the current zoom box
        mertiles_to_load = self._find_intersecting_tiles(data, zoom_data['ra_min'], zoom_data['ra_max'], 
                                                        zoom_data['dec_min'], zoom_data['dec_max'])
        print(f"Debug: Found {len(mertiles_to_load)} MER tiles in zoom area for coverage loading")

        # Load data with coverage for each MER tile
        self._load_tile_data_with_coverage(mertiles_to_load, data, catred_scatter_data, maglim, threshold)
        
        # Store current data for click callbacks
        self.current_catred_data = catred_scatter_data
        
        print(f"Debug: Total CATRED points with coverage loaded: {len(catred_scatter_data['ra'])}")
        return catred_scatter_data

    def _load_tile_data_with_coverage(self, mertiles_to_load: List[int], data: Dict[str, Any],
                                    catred_scatter_data: Dict[str, List], maglim: float = 24.0, threshold: float = 0.8) -> None:
        """Load data with coverage for each MER tile and accumulate in scatter data."""
        for mertileid in mertiles_to_load:
            tile_data = self.get_radec_mertile_with_coverage(mertileid, data, maglim, threshold)
            if tile_data and 'RIGHT_ASCENSION' in tile_data:
                catred_scatter_data['ra'].extend(tile_data['RIGHT_ASCENSION'])
                catred_scatter_data['dec'].extend(tile_data['DECLINATION'])
                catred_scatter_data['phz_mode_1'].extend(tile_data['PHZ_MODE_1'])
                catred_scatter_data['phz_median'].extend(tile_data['PHZ_MEDIAN'])
                catred_scatter_data['phz_70_int'].extend(tile_data['PHZ_70_INT'])
                catred_scatter_data['phz_pdf'].extend(tile_data['PHZ_PDF'])
                catred_scatter_data['kron_radius'].extend(tile_data['KRON_RADIUS'])
                catred_scatter_data['effective_coverage'].extend(tile_data['EFFECTIVE_COVERAGE'])
                print(f"Debug: Added {len(tile_data['RIGHT_ASCENSION'])} sources with coverage from MER tile {mertileid}")

    def update_catred_data_clusterbox(self, box: Dict[str, Any], data: Dict[str, Any],
                                      threshold: float = 0.8, maglim: float = 24.0) -> Dict[str, List]:
        """
        Update CATRED data for the given cluster box selection.
        
        Args:
            box: Dictionary containing box window parameters
            data: Main data dictionary containing MER tile information
            threshold: Effective coverage threshold for masked data (default 0.8)
            maglim: Magnitude limit for filtering (default 24.0)

        Returns:
            Dictionary with scatter plot data for CATRED points within the box
        """
        if not box or not all(k in box for k in ['ra_min', 'ra_max', 'dec_min', 'dec_max', 'z_min', 'z_max', 'trace_marker_size', 'trace_marker_color']):
            print("Debug: No valid box data for CATRED")
            print("Debug: Box data received:", box)
            return {'ra': [], 'dec': [], 'phz_mode_1': [], 'phz_median': [], 'phz_70_int': [], 'phz_pdf': [], 'kron_radius': [], 'effective_coverage': [], 'trace_marker_size': [], 'trace_marker_color': []}
        
        # Find MER tiles that intersect with box area
        mertiles_to_load = self._find_intersecting_tiles(data, box['ra_min'], box['ra_max'], box['dec_min'], box['dec_max'])

        if not mertiles_to_load:
            print("Debug: No intersecting MER tiles found for CATRED")
            return {'ra': [], 'dec': [], 'phz_mode_1': [], 'phz_median': [], 'phz_70_int': [], 'phz_pdf': [], 'kron_radius': [], 'effective_coverage': [], 'trace_marker_size': [], 'trace_marker_color': []}

        print(f"Debug: Loading CATRED for {len(mertiles_to_load)} MER tiles")

        # Initialize scatter data container
        catred_scatter_data = {'ra': [], 'dec': [], 'phz_mode_1': [], 'phz_median': [], 'phz_70_int': [], 'phz_pdf': [], 'kron_radius': [], 'effective_coverage': [], 'trace_marker_size': [], 'trace_marker_color': []}

        # Load data for each intersecting tile using masked method
        self._load_tile_data_clusterbox(mertiles_to_load, data, catred_scatter_data, threshold, maglim, box)

        print(f"Debug: Total CATRED points loaded: {len(catred_scatter_data['ra'])}")
        return catred_scatter_data

    def _load_tile_data_clusterbox(self, mertiles_to_load: List[int], data: Dict[str, Any],
                                   catred_scatter_data: Dict[str, List], threshold: float = 0.8, 
                                   maglim: float = 24.0, box: Dict[str, Any] = None) -> None:
        """Load masked data for each MER tile and accumulate in scatter data."""
        for mertileid in mertiles_to_load:
            tile_data = self.get_radec_mertile_masked(mertileid=mertileid, data=data, 
                                                      threshold=threshold, maglim=maglim, box=box)
            if tile_data and 'RIGHT_ASCENSION' in tile_data:
                catred_scatter_data['ra'].extend(tile_data['RIGHT_ASCENSION'])
                catred_scatter_data['dec'].extend(tile_data['DECLINATION'])
                catred_scatter_data['phz_mode_1'].extend(tile_data['PHZ_MODE_1'])
                catred_scatter_data['phz_median'].extend(tile_data['PHZ_MEDIAN'])
                catred_scatter_data['phz_70_int'].extend(tile_data['PHZ_70_INT'])
                catred_scatter_data['phz_pdf'].extend(tile_data['PHZ_PDF'])
                catred_scatter_data['kron_radius'].extend(tile_data['KRON_RADIUS'])
                catred_scatter_data['effective_coverage'].extend(tile_data['EFFECTIVE_COVERAGE'])

                if 'trace_marker_size' in box and type(box['trace_marker_size']) == float:
                    catred_scatter_data['trace_marker_size'].extend([box['trace_marker_size']] * len(tile_data['RIGHT_ASCENSION']))
                elif 'trace_marker_size' in box and box['trace_marker_size'] == 'variable':
                    catred_scatter_data['trace_marker_size'].extend(tile_data['KRON_RADIUS'])
                else:
                    catred_scatter_data['trace_marker_size'].extend([10] * len(tile_data['RIGHT_ASCENSION']))

                if 'trace_marker_color' in box and type(box['trace_marker_color']) == str:
                    catred_scatter_data['trace_marker_color'].append(box['trace_marker_color'])

                print(f"Debug: Added {len(tile_data['RIGHT_ASCENSION'])} masked points from MER tile {mertileid}")

    def update_catred_data_unmasked(self, zoom_data: Dict[str, Any], data: Dict[str, Any], maglim: float = 24.0) -> Dict[str, List]:
        """
        Update unmasked CATRED data for the given zoom window.
        
        Args:
            zoom_data: Dictionary containing zoom window parameters
            data: Main data dictionary containing MER tile information
            maglim: Magnitude limit for filtering (default 24.0)
            
        Returns:
            Dictionary with scatter plot data for unmasked CATRED points
        """
        # Find MER tiles that intersect with zoom area
        if not zoom_data or not all(k in zoom_data for k in ['ra_min', 'ra_max', 'dec_min', 'dec_max']):
            print("Debug: No valid zoom data for unmasked CATRED")
            return {'ra': [], 'dec': [], 'phz_mode_1': [], 'phz_median': [], 'phz_70_int': [], 'phz_pdf': [], 'kron_radius': [], 'effective_coverage': []}
            
        mertiles_to_load = self._find_intersecting_tiles(data, zoom_data['ra_min'], zoom_data['ra_max'], 
                                                        zoom_data['dec_min'], zoom_data['dec_max'])
        
        if not mertiles_to_load:
            print("Debug: No intersecting MER tiles found for unmasked CATRED")
            return {'ra': [], 'dec': [], 'phz_mode_1': [], 'phz_median': [], 'phz_70_int': [], 'phz_pdf': [], 'kron_radius': [], 'effective_coverage': []}
        
        print(f"Debug: Loading unmasked CATRED for {len(mertiles_to_load)} MER tiles")
        
        # Initialize scatter data container
        catred_scatter_data = {'ra': [], 'dec': [], 'phz_mode_1': [], 'phz_median': [], 'phz_70_int': [], 'phz_pdf': [], 'kron_radius': [], 'effective_coverage': []}
        
        # Load data for each intersecting tile using unmasked method
        self._load_tile_data_unmasked(mertiles_to_load, data, catred_scatter_data, maglim)
        
        # Store current data for click callbacks
        self.current_catred_data = catred_scatter_data
        
        print(f"Debug: Total unmasked CATRED points loaded: {len(catred_scatter_data['ra'])}")
        return catred_scatter_data

    def _load_tile_data_unmasked(self, mertiles_to_load: List[int], data: Dict[str, Any], 
                                catred_scatter_data: Dict[str, List], maglim: float = 24.0) -> None:
        """Load unmasked data for each MER tile and accumulate in scatter data."""
        for mertileid in mertiles_to_load:
            tile_data = self.get_radec_mertile(mertileid, data, maglim)
            if tile_data and 'RIGHT_ASCENSION' in tile_data:
                catred_scatter_data['ra'].extend(tile_data['RIGHT_ASCENSION'])
                catred_scatter_data['dec'].extend(tile_data['DECLINATION'])
                catred_scatter_data['phz_mode_1'].extend(tile_data['PHZ_MODE_1'])
                catred_scatter_data['phz_median'].extend(tile_data['PHZ_MEDIAN'])
                catred_scatter_data['phz_70_int'].extend(tile_data['PHZ_70_INT'])
                catred_scatter_data['phz_pdf'].extend(tile_data['PHZ_PDF'])
                catred_scatter_data['kron_radius'].extend(tile_data['KRON_RADIUS'])
                catred_scatter_data['effective_coverage'].extend(tile_data['EFFECTIVE_COVERAGE'])  # Dummy coverage for unmasked data
                print(f"Debug: Added {len(tile_data['RIGHT_ASCENSION'])} unmasked points from MER tile {mertileid}")

    def load_catred_scatter_data(self, data: Dict[str, Any], relayout_data: Dict[str, Any],
                                catred_masked: bool = True, threshold: float = 0.8, maglim: float = 24.0) -> Dict[str, List]:
        """
        Load CATRED scatter data based on the specified mode.
        
        Args:
            data: Main data dictionary containing MER tile information
            relayout_data: Current zoom/pan state for determining zoom window
            catred_masked: CATRED data, masked (True) or unmasked (False)
            threshold: Effective coverage threshold for masked data (default 0.8)
            maglim: Magnitude limit for filtering (default 24.0)
            
        Returns:
            Dictionary with scatter plot data for CATRED points
        """
        try:
            assert type(catred_masked) == bool, "catred_masked must be a boolean"
            # Extract zoom data from relayout_data
            zoom_data = self._extract_zoom_data_from_relayout(relayout_data)

            if catred_masked:
                print(f"Debug: Loading masked CATRED data with coverage for client-side filtering")
                return self.update_catred_data_with_coverage(zoom_data, data, maglim, threshold)
            else:  # unmasked
                print("Debug: Loading unmasked CATRED data")
                return self.update_catred_data_unmasked(zoom_data, data, maglim=1000.0)  # Use high maglim for unmasked to avoid filtering
        except:
            print(f"Debug: catred_masked not a boolean, executing catred_masked='True' fallback")
            return {'ra': [], 'dec': [], 'phz_mode_1': [], 'phz_median': [], 'phz_70_int': [], 'phz_pdf': [], 'kron_radius': [], 'effective_coverage': []}
        
        

    def load_catred_data_clusterbox(self, box: Dict[str, Any], data: Dict[str, Any], catred_masked: bool = True,
                                   threshold: float = 0.8, maglim: float = 24.0) -> Dict[str, List]:
        """
        Load CATRED data for a specific cluster box.

        Args:
            box: Dictionary containing box window parameters
            data: Main data dictionary containing MER tile information
            threshold: Effective coverage threshold for masked data (default 0.8)
            maglim: Magnitude limit for filtering (default 24.0)

        Returns:
            Dictionary with scatter plot data for CATRED points
        """
        print("Debug: Loading masked (default) CATRED data for cluster box selection")
        return self.update_catred_data_clusterbox(box, data, threshold, maglim)

    def apply_box_selection(
            self, src: Table, box: Dict[str, float]
            ) -> Table:
        """Apply RA/Dec box selection to the source table."""
        ra_min = box['ra_min']
        ra_max = box['ra_max']
        dec_min = box['dec_min']
        dec_max = box['dec_max']
        z_min = box['z_min']
        z_max = box['z_max']

        # self.catred_z_param_select_for_filter = 'PHZ_MODE_1'

        selection_mask = (
            (src['RIGHT_ASCENSION'] >= ra_min) & (src['RIGHT_ASCENSION'] <= ra_max) &
            (src['DECLINATION'] >= dec_min) & (src['DECLINATION'] <= dec_max) & 
            (src[self.catred_z_param_select_for_filter] >= z_min) & (src[self.catred_z_param_select_for_filter] <= z_max)
        )
        
        filtered_src = src[selection_mask]
        print(f"Debug: Applied box selection: {len(filtered_src)} sources remain after filtering")
        return filtered_src
    
    def _extract_box_data_from_cluster_click(self, click_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract box window parameters from cluster click data.
        
        Args:
            click_data: Plotly click data containing box selection
        Returns:
            Dictionary with box window parameters
        """
        if not click_data:
            return {}

        ra_min = click_data['ra'] - click_data['catred_box_size'] / 2
        ra_max = click_data['ra'] + click_data['catred_box_size'] / 2
        dec_min = click_data['dec'] - click_data['catred_box_size'] / 2
        dec_max = click_data['dec'] + click_data['catred_box_size'] / 2
        z_min = max(click_data['redshift'] - click_data['catred_redshift_bin_width'] / 2, click_data['redshift_lim_lower'])
        z_max = min(click_data['redshift'] + click_data['catred_redshift_bin_width'] / 2, click_data['redshift_lim_upper'])

        if 'trace_marker' in click_data:
            if click_data['trace_marker']['size_option'] == 'set_size_custom':
                trace_catred_marker_size = click_data['trace_marker']['size_custom_value']
            elif click_data['trace_marker']['size_option'] == 'set_size_kronradius':
                trace_catred_marker_size = 'variable'  # Use default sizing
        else:
            trace_catred_marker_size = 10  # Use default sizing
        
        if 'trace_marker' in click_data and 'color' in click_data['trace_marker']:
            trace_catred_marker_color = click_data['trace_marker']['color']
        else:
            trace_catred_marker_color = 'yellow'  # Default color

        return {
            'ra_min': ra_min,
            'ra_max': ra_max,
            'dec_min': dec_min,
            'dec_max': dec_max,
            'z_min': z_min,
            'z_max': z_max,
            'trace_marker_size': trace_catred_marker_size,
            'trace_marker_color': trace_catred_marker_color
        }

    def _extract_zoom_data_from_relayout(self, relayout_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract zoom window parameters from relayout data.
        
        Args:
            relayout_data: Plotly relayout data containing zoom state
            
        Returns:
            Dictionary with zoom window parameters
        """
        if not relayout_data:
            return {}
        
        zoom_data = {}
        
        # Extract zoom ranges
        if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
            zoom_data['ra_min'] = relayout_data['xaxis.range[0]']
            zoom_data['ra_max'] = relayout_data['xaxis.range[1]']
        
        if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
            zoom_data['dec_min'] = relayout_data['yaxis.range[0]']
            zoom_data['dec_max'] = relayout_data['yaxis.range[1]']
        
        return zoom_data
    
    def clear_traces_cache(self) -> None:
        """Clear the CATRED traces cache."""
        self.traces_cache = []
        print("CATRED traces cache cleared")

    def get_traces_count(self) -> int:
        """Get the number of cached CATRED traces."""
        return len(self.traces_cache)


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