"""
Python class to handle the extraction and visualization of mosaic images.
"""

import glob
import os
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy import wcs
import plotly.graph_objs as go
from typing import Dict, List, Any, Optional, Tuple
from shapely.geometry import box

try:
    from cluster_visualization.src import config
    from cluster_visualization.src.config import Config
except ImportError:
    from cluster_visualization.src.config import Config
    config = Config()


class MOSAICHandler:
    """Handler for MER mosaic image data, similar to CATREDHandler."""
    
    def __init__(self, config=None, useconfig=True):
        """Initiate MOSAICHandler"""
        self.traces_cache = []  # Store accumulated mosaic image traces
        self.current_mosaic_data = None  # Store current mosaic data for interactions
        if useconfig:
            self.config = config if config else Config() 

        self.mosaic_header = None
        self.mosaic_data = None
        self.mosaic_wcs = None

        # Image processing parameters
        self.img_width = 3840
        self.img_height = 3840
        self.img_scale = 5.0
        self.n_sigma = 1.0  # Number of standard deviations for clipping

    def get_mosaic_fits_data_by_mertile(self, mertileid):
        """Load mosaic FITS data for a specific MER tile ID."""
        mosaic_dir = self.config.mosaic_dir
        fits_files = glob.glob(os.path.join(mosaic_dir, f'EUC_MER_BGSUB-MOSAIC-VIS_TILE{mertileid}*.fits.gz'))
        
        if not fits_files:
            print(f"Warning: No mosaic FITS file found for MER tile {mertileid}")
            return None
            
        fits_file = fits_files[0]  # Take the first match
        
        try:
            # Use memmap=False to avoid memory mapping issues with compressed files
            with fits.open(fits_file, ignore_missing_simple=True, memmap=False) as hdul:
                primary_hdu = hdul[0]
                self.mosaic_header = primary_hdu.header.copy()
                # Create a copy of the data to avoid issues with file closure
                self.mosaic_data = primary_hdu.data.copy() if primary_hdu.data is not None else None
                self.mosaic_wcs = wcs.WCS(primary_hdu.header)
                
                if self.mosaic_data is None:
                    print(f"Warning: No data in primary HDU for {fits_file}")
                    return None
                    
                return {
                    'header': self.mosaic_header,
                    'data': self.mosaic_data,
                    'wcs': self.mosaic_wcs,
                    'file_path': fits_file
                }
        except Exception as e:
            print(f"Error loading mosaic FITS file {fits_file}: {e}")
            return None

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
        
        if all(v is not None for v in [ra_min, ra_max, dec_min, dec_max]):
            return (ra_min, ra_max, dec_min, dec_max)
        return None

    def _find_intersecting_tiles(self, data: Dict[str, Any], ra_min: float, ra_max: float, 
                                dec_min: float, dec_max: float) -> List[int]:
        """Find MER tiles whose polygons intersect with the zoom box."""
        zoom_box = box(ra_min, dec_min, ra_max, dec_max)
        mertiles_to_load = []
        
        # Check if catred_info exists in data (contains tile polygons)
        if 'catred_info' not in data:
            print("Warning: No catred_info found in data for tile intersection")
            return mertiles_to_load
        
        for mertileid, row in data['catred_info'].iterrows():
            poly = row['polygon']
            if poly is not None:
                # Use proper geometric intersection
                if poly.intersects(zoom_box):
                    mertiles_to_load.append(mertileid)

        print(f"Debug: Found {len(mertiles_to_load)} MER tiles with mosaics in zoom area: "
              f"{mertiles_to_load[:5]}{'...' if len(mertiles_to_load) > 5 else ''}")
        
        return mertiles_to_load

    def _process_mosaic_image(self, mosaic_data: np.ndarray, target_width: int = None, 
                             target_height: int = None) -> np.ndarray:
        """Process mosaic image data for visualization."""
        if target_width is None:
            target_width = self.img_width
        if target_height is None:
            target_height = self.img_height
            
        try:
            # Ensure we have a valid numpy array
            if not isinstance(mosaic_data, np.ndarray):
                print(f"Warning: mosaic_data is not ndarray, type: {type(mosaic_data)}")
                return np.zeros((target_height, target_width))
            
            # Handle NaN values
            valid_mask = np.isfinite(mosaic_data)
            valid_data = mosaic_data[valid_mask]
            
            if len(valid_data) == 0:
                print("Warning: No valid data found in mosaic image")
                return np.zeros((target_height, target_width))
            
            # Calculate statistics on valid data only
            mean = np.mean(valid_data)
            std = np.std(valid_data)
            
            # Clip the data to the range [0, mean + n_sigma * std]
            max_val = mean + self.n_sigma * std
            if max_val <= 0:
                max_val = np.max(valid_data)
            
            clipped = np.clip(mosaic_data, 0.0, max_val)
            
            # Normalize to [0, 1]
            normalized = clipped / max_val
            
            # Replace any remaining NaN/inf values with 0
            normalized = np.where(np.isfinite(normalized), normalized, 0.0)
            
            # Resize image using PIL for high quality
            pil_image = Image.fromarray(normalized)
            resized_pil = pil_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Convert back to numpy array and flip for proper orientation
            resized_array = np.array(resized_pil.transpose(Image.FLIP_TOP_BOTTOM))
            
            return resized_array
            
        except Exception as e:
            print(f"Error processing mosaic image: {e}")
            return np.zeros((target_height, target_width))

    def _calculate_image_bounds(self, mosaic_wcs: wcs.WCS, header: fits.Header, 
                               target_width: int, target_height: int) -> Dict[str, float]:
        """Calculate coordinate bounds for the processed image."""
        # Calculate scaling factors
        scale_x = header['NAXIS1'] / target_width
        scale_y = header['NAXIS2'] / target_height
        
        # Create binned header for resized image
        header_binned = header.copy()
        header_binned['NAXIS1'] = target_width
        header_binned['NAXIS2'] = target_height
        
        # Update WCS parameters for binning
        if 'CRPIX1' in header_binned:
            header_binned['CRPIX1'] /= scale_x
        if 'CRPIX2' in header_binned:
            header_binned['CRPIX2'] /= scale_y
        
        # Update CD matrix elements
        for key in ['CD1_1', 'CD1_2', 'CD2_1', 'CD2_2']:
            if key in header_binned:
                if '1_' in key:
                    header_binned[key] *= scale_x
                else:
                    header_binned[key] *= scale_y
        
        # Create WCS for binned image
        wcs_binned = wcs.WCS(header_binned)
        
        # Define corner pixels
        corners_pix = np.array([
            [0, 0],                    # Bottom-left
            [target_width, 0],         # Bottom-right
            [target_width, target_height],  # Top-right
            [0, target_height]         # Top-left
        ])
        
        try:
            # Convert to world coordinates
            corners_world = wcs_binned.pixel_to_world_values(corners_pix)
            
            # Handle different return formats from astropy
            if corners_world.ndim == 1:
                # Single coordinate pair format
                ra_coords = [corners_world[0] for _ in range(4)]
                dec_coords = [corners_world[1] for _ in range(4)]
            elif corners_world.ndim == 2 and corners_world.shape[1] >= 2:
                # Array of coordinate pairs
                ra_coords = corners_world[:, 0]
                dec_coords = corners_world[:, 1]
            else:
                # Alternative: use individual pixel conversions
                ra_coords = []
                dec_coords = []
                for corner in corners_pix:
                    world_coord = wcs_binned.pixel_to_world_values(corner[0], corner[1])
                    if isinstance(world_coord, (list, tuple)) and len(world_coord) >= 2:
                        ra_coords.append(world_coord[0])
                        dec_coords.append(world_coord[1])
                    else:
                        ra_coords.append(world_coord)
                        dec_coords.append(world_coord)
            
            return {
                'ra_min': np.min(ra_coords),
                'ra_max': np.max(ra_coords),
                'dec_min': np.min(dec_coords),
                'dec_max': np.max(dec_coords),
                'wcs_binned': wcs_binned
            }
        except Exception as e:
            print(f"Warning: Error calculating image bounds: {e}")
            # Fallback to approximate bounds based on central pixel
            try:
                center_x, center_y = target_width // 2, target_height // 2
                center_world = wcs_binned.pixel_to_world_values(center_x, center_y)
                if isinstance(center_world, (list, tuple)) and len(center_world) >= 2:
                    center_ra, center_dec = center_world[0], center_world[1]
                else:
                    center_ra, center_dec = center_world, center_world
                
                # Estimate bounds around center (rough approximation)
                ra_range = dec_range = 0.1  # degrees
                return {
                    'ra_min': center_ra - ra_range,
                    'ra_max': center_ra + ra_range,
                    'dec_min': center_dec - dec_range,
                    'dec_max': center_dec + dec_range,
                    'wcs_binned': wcs_binned
                }
            except Exception:
                # Final fallback to generic bounds
                return {
                    'ra_min': 0, 'ra_max': 360,
                    'dec_min': -90, 'dec_max': 90,
                    'wcs_binned': wcs_binned
                }

    def create_mosaic_image_trace(self, mertileid: int, opacity: float = 0.5, 
                                 colorscale: str = 'gray') -> Optional[go.Heatmap]:
        """Create a Plotly heatmap trace for a mosaic image."""
        # Load mosaic data for this tile
        mosaic_info = self.get_mosaic_fits_data_by_mertile(mertileid)
        if not mosaic_info:
            return None
        
        # Process the image
        processed_image = self._process_mosaic_image(mosaic_info['data'])
        
        # Calculate coordinate bounds
        bounds = self._calculate_image_bounds(
            mosaic_info['wcs'], 
            mosaic_info['header'],
            self.img_width, 
            self.img_height
        )
        
        # Create coordinate arrays for the heatmap
        height, width = processed_image.shape
        x_coords = np.linspace(bounds['ra_min'], bounds['ra_max'], width)
        y_coords = np.linspace(bounds['dec_min'], bounds['dec_max'], height)
        
        # Create the heatmap trace
        trace = go.Heatmap(
            z=processed_image,
            x=x_coords,
            y=y_coords,
            opacity=opacity,
            colorscale=colorscale,
            showscale=False,  # Don't show colorbar
            name=f"Mosaic {mertileid}",
            hovertemplate=(
                f"MER Tile: {mertileid}<br>"
                "RA: %{x:.4f}°<br>"
                "Dec: %{y:.4f}°<br>"
                "Intensity: %{z:.3f}<br>"
                "<extra>Mosaic Image</extra>"
            )
        )
        
        return trace

    def load_mosaic_traces_in_zoom(self, data: Dict[str, Any], relayout_data: Optional[Dict], 
                                  opacity: float = 0.5, colorscale: str = 'gray') -> List[go.Heatmap]:
        """Load mosaic image traces for MER tiles visible in the current zoom window."""
        traces = []
        
        if not relayout_data:
            print("Debug: No relayout data available for mosaic loading")
            return traces
        
        # Extract zoom ranges from relayout data
        zoom_ranges = self._extract_zoom_ranges(relayout_data)
        if not zoom_ranges:
            print("Debug: Could not extract zoom ranges for mosaic loading")
            return traces
        
        ra_min, ra_max, dec_min, dec_max = zoom_ranges
        print(f"Debug: Loading mosaics for zoom area: RA({ra_min:.3f}, {ra_max:.3f}), "
              f"Dec({dec_min:.3f}, {dec_max:.3f})")
        
        # Find intersecting tiles
        mertiles_to_load = self._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)
        
        if not mertiles_to_load:
            print("Debug: No MER tiles with mosaics found in zoom area")
            return traces
        
        # Limit to avoid loading too many mosaics at once
        max_mosaics = 3  # Limit for performance
        if len(mertiles_to_load) > max_mosaics:
            print(f"Debug: Limiting to first {max_mosaics} mosaics for performance")
            mertiles_to_load = mertiles_to_load[:max_mosaics]
        
        # Create traces for each mosaic
        for mertileid in mertiles_to_load:
            try:
                trace = self.create_mosaic_image_trace(mertileid, opacity, colorscale)
                if trace:
                    traces.append(trace)
                    print(f"Debug: Created mosaic trace for MER tile {mertileid}")
            except Exception as e:
                print(f"Warning: Failed to create mosaic trace for tile {mertileid}: {e}")
        
        return traces

    def clear_traces_cache(self):
        """Clear the mosaic traces cache."""
        self.traces_cache = []
        self.current_mosaic_data = None

    
# Example usage and testing code (can be removed in production)
if __name__ == "__main__":
    # Test the MOSAICHandler
    handler = MOSAICHandler()
    
    # Example MER tile ID
    test_mertileid = 102011610
    
    # Test loading mosaic data
    mosaic_info = handler.get_mosaic_fits_data_by_mertile(test_mertileid)
    if mosaic_info:
        print(f"Successfully loaded mosaic for MER tile {test_mertileid}")
        print(f"Image shape: {mosaic_info['data'].shape}")
        
        # Test creating a trace
        trace = handler.create_mosaic_image_trace(test_mertileid)
        if trace:
            print("Successfully created mosaic trace")
        else:
            print("Failed to create mosaic trace")
    else:
        print(f"Failed to load mosaic for MER tile {test_mertileid}")
