"""
Python class to handle the extraction and visualization of mosaic images.
"""

import glob
import os
import tempfile
import base64
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy import wcs
import plotly.graph_objs as go
from typing import Dict, List, Any, Optional, Tuple
from shapely.geometry import box
import io

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
        self.img_width = 1920   # Reduced from 3840 for faster processing
        self.img_height = 1920  # Reduced from 3840 for faster processing
        self.img_scale = 5.0
        self.n_sigma = 1.0  # Number of standard deviations for clipping
        
        # PNG rendering parameters for fast display
        self.png_dpi = 150  # High quality but not excessive
        self.png_cache = {}  # Cache PNG images to avoid re-rendering

    def get_mosaic_fits_data_by_mertile(self, mertileid):
        """Load mosaic FITS data for a specific MER tile ID."""
        mosaic_dir = self.config.mosaic_dir
        fits_files = glob.glob(os.path.join(mosaic_dir, f'EUC_MER_BGSUB-MOSAIC-VIS_TILE{mertileid}*.fits.gz'))
        
        if not fits_files:
            print(f"Warning: No mosaic FITS file found for MER tile {mertileid}")
            return None
            
        fits_file = fits_files[0]  # Take the first match
        file_size_gb = os.path.getsize(fits_file) / (1024**3)
        print(f"Loading mosaic file ({file_size_gb:.2f} GB): {os.path.basename(fits_file)}")
        
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
        """Process mosaic image data for visualization using the scaling approach from the notebook."""
        if target_width is None:
            target_width = self.img_width
        if target_height is None:
            target_height = self.img_height
            
        try:
            # Ensure we have a valid numpy array
            if not isinstance(mosaic_data, np.ndarray):
                print(f"Warning: mosaic_data is not ndarray, type: {type(mosaic_data)}")
                return np.zeros((target_height, target_width))
            
            print(f"Debug: Original mosaic dimensions: {mosaic_data.shape[1]} x {mosaic_data.shape[0]} pixels")
            print(f"Debug: Target dimensions: {target_width} x {target_height} pixels")
            
            # Handle NaN values - similar to notebook approach
            valid_mask = np.isfinite(mosaic_data)
            if not np.any(valid_mask):
                print("Warning: No valid data found in mosaic image")
                return np.zeros((target_height, target_width))
            
            print("Debug: Computing statistics...")
            
            # Apply sigma clipping and normalization as in notebook cell 59
            # Use ravel to flatten the array for mean and std calculations
            # For large arrays, sample a subset for statistics to speed up processing
            if mosaic_data.size > 10_000_000:  # If larger than 10M pixels
                print("Debug: Large image detected, sampling for statistics...")
                # Sample every 10th pixel for statistics
                sample_data = mosaic_data[::10, ::10].ravel()
                mean = np.mean(sample_data)
                std = np.std(sample_data)
            else:
                mean = np.mean(mosaic_data.ravel())
                std = np.std(mosaic_data.ravel())
            
            print(f"Debug: Mosaic data statistics - mean: {mean:.3f}, std: {std:.3f}")
            
            # Clip the data to the range [0, mean + N * std] where N = n_sigma
            max_val = mean + self.n_sigma * std
            print(f"Debug: Clipping data to range [0, {max_val:.3f}]")
            
            mer_image = np.clip(mosaic_data, 0.0, max_val)
            
            # Normalize the image as in the notebook
            mer_image = mer_image / max_val
            
            print(f"Debug: After clipping and normalization - range: [{np.min(mer_image):.3f}, {np.max(mer_image):.3f}]")
            
            print("Debug: Starting image resize...")
            
            # Resize the image to match target dimensions using the same approach as notebook
            # Convert to PIL Image, resize with LANCZOS, and transpose with FLIP_TOP_BOTTOM
            mer_array = np.array(
                Image.fromarray(mer_image)
                .resize((target_width, target_height), Image.Resampling.LANCZOS)
                .transpose(Image.FLIP_TOP_BOTTOM)
            )
            
            print(f"Debug: Final processed image shape: {mer_array.shape}")
            
            # Clean up large arrays to free memory
            del mer_image
            if 'sample_data' in locals():
                del sample_data
            
            return mer_array
            
        except Exception as e:
            print(f"Error processing mosaic image: {e}")
            import traceback
            traceback.print_exc()
            return np.zeros((target_height, target_width))

    def _create_scaled_wcs(self, original_header: fits.Header, original_shape: Tuple[int, int],
                          target_width: int, target_height: int) -> wcs.WCS:
        """Create a scaled WCS header similar to the notebook's header_binned approach."""
        try:
            # Calculate scaling factors based on the original and target dimensions
            orig_height, orig_width = original_shape
            scale_x = orig_width / target_width
            scale_y = orig_height / target_height
            
            print(f"Debug: WCS scaling factors - scale_x: {scale_x:.3f}, scale_y: {scale_y:.3f}")
            
            # Create a modified header (binned header) similar to notebook
            header_binned = original_header.copy()
            header_binned['NAXIS1'] = target_width
            header_binned['NAXIS2'] = target_height
            
            # Adjust WCS parameters for the scaling
            if 'CRPIX1' in header_binned:
                header_binned['CRPIX1'] /= scale_x
            if 'CRPIX2' in header_binned:
                header_binned['CRPIX2'] /= scale_y
                
            # Scale the CD matrix elements
            if 'CD1_1' in header_binned:
                header_binned['CD1_1'] *= scale_x
            if 'CD1_2' in header_binned:
                header_binned['CD1_2'] *= scale_x
            if 'CD2_1' in header_binned:
                header_binned['CD2_1'] *= scale_y
            if 'CD2_2' in header_binned:
                header_binned['CD2_2'] *= scale_y
                
            # Alternative: if using CDELT instead of CD matrix
            if 'CDELT1' in header_binned and 'CD1_1' not in header_binned:
                header_binned['CDELT1'] *= scale_x
            if 'CDELT2' in header_binned and 'CD2_2' not in header_binned:
                header_binned['CDELT2'] *= scale_y
            
            # Create the scaled WCS
            wcs_binned = wcs.WCS(header_binned)
            
            print(f"Debug: Created scaled WCS for {target_width}x{target_height} image")
            
            return wcs_binned
            
        except Exception as e:
            print(f"Warning: Failed to create scaled WCS, using original: {e}")
            # Fallback to original WCS
            return wcs.WCS(original_header)
    def _calculate_image_bounds(self, mosaic_wcs: wcs.WCS, header: fits.Header, 
                               target_width: int, target_height: int) -> Dict[str, float]:
        """Calculate coordinate bounds for the processed image using scaled WCS approach from notebook."""
        try:
            # Get the original image dimensions
            naxis1 = header['NAXIS1']  # Width in pixels
            naxis2 = header['NAXIS2']  # Height in pixels
            
            print(f"Debug: Original mosaic dimensions: {naxis1} x {naxis2} pixels")
            
            # Create scaled WCS similar to notebook's header_binned approach
            original_shape = (naxis2, naxis1)  # (height, width)
            scaled_wcs = self._create_scaled_wcs(header, original_shape, target_width, target_height)
            
            # Define corner pixels of the SCALED/BINNED image
            corners_pix = np.array([
                [0.5, 0.5],                        # Bottom-left
                [target_width + 0.5, 0.5],        # Bottom-right
                [target_width + 0.5, target_height + 0.5], # Top-right
                [0.5, target_height + 0.5]        # Top-left
            ])
            
            # Convert corner pixels to world coordinates using scaled WCS
            corners_world = scaled_wcs.pixel_to_world_values(corners_pix)
            
            # Handle different return formats from astropy
            if isinstance(corners_world, np.ndarray):
                if corners_world.ndim == 2 and corners_world.shape[1] >= 2:
                    # Array of coordinate pairs [N, 2]
                    ra_coords = corners_world[:, 0]
                    dec_coords = corners_world[:, 1]
                else:
                    # 1D array or other format, convert each corner individually
                    ra_coords, dec_coords = [], []
                    for i, corner in enumerate(corners_pix):
                        world_coord = scaled_wcs.pixel_to_world_values(corner[0], corner[1])
                        if isinstance(world_coord, (list, tuple)) and len(world_coord) >= 2:
                            ra_coords.append(world_coord[0])
                            dec_coords.append(world_coord[1])
                        else:
                            ra_coords.append(world_coord)
                            dec_coords.append(world_coord)
            elif isinstance(corners_world, (tuple, list)):
                # Return is a tuple/list - convert each corner individually
                ra_coords, dec_coords = [], []
                for corner in corners_pix:
                    world_coord = scaled_wcs.pixel_to_world_values(corner[0], corner[1])
                    if isinstance(world_coord, (list, tuple)) and len(world_coord) >= 2:
                        ra_coords.append(world_coord[0])
                        dec_coords.append(world_coord[1])
                    else:
                        print(f"Warning: Unexpected single coordinate: {world_coord}")
                        ra_coords.append(0.0)
                        dec_coords.append(0.0)
            else:
                # Fallback: convert each corner individually
                ra_coords = []
                dec_coords = []
                for corner in corners_pix:
                    try:
                        world_coord = scaled_wcs.pixel_to_world_values(corner[0], corner[1])
                        if isinstance(world_coord, (list, tuple)) and len(world_coord) >= 2:
                            ra_coords.append(world_coord[0])
                            dec_coords.append(world_coord[1])
                        else:
                            # Single value returned - this shouldn't happen for 2D coordinates
                            print(f"Warning: Unexpected WCS conversion result: {world_coord}")
                            ra_coords.append(0.0)
                            dec_coords.append(0.0)
                    except Exception as e:
                        print(f"Warning: Failed to convert corner {corner}: {e}")
                        ra_coords.append(0.0)
                        dec_coords.append(0.0)
            
            # Calculate bounds
            ra_min = np.min(ra_coords)
            ra_max = np.max(ra_coords)
            dec_min = np.min(dec_coords)
            dec_max = np.max(dec_coords)
            
            # Calculate the actual tile size in degrees
            ra_size = ra_max - ra_min
            dec_size = dec_max - dec_min
            
            print(f"Debug: Mosaic tile bounds: RA({ra_min:.6f}, {ra_max:.6f}) = {ra_size:.6f}°")
            print(f"Debug: Mosaic tile bounds: Dec({dec_min:.6f}, {dec_max:.6f}) = {dec_size:.6f}°")
            
            # Handle potential RA wraparound near 0/360 degrees
            if ra_max - ra_min > 180:
                print("Debug: Detected RA wraparound, adjusting coordinates")
                # Find coordinates < 180 and > 180, adjust the smaller ones
                ra_coords = np.array(ra_coords)
                if np.any(ra_coords < 180) and np.any(ra_coords > 180):
                    ra_coords = np.where(ra_coords < 180, ra_coords + 360, ra_coords)
                    ra_min = np.min(ra_coords)
                    ra_max = np.max(ra_coords)
                    ra_size = ra_max - ra_min
                    print(f"Debug: Adjusted RA bounds: ({ra_min:.6f}, {ra_max:.6f}) = {ra_size:.6f}°")
            
            return {
                'ra_min': ra_min,
                'ra_max': ra_max,
                'dec_min': dec_min,
                'dec_max': dec_max,
                'ra_size_deg': ra_size,
                'dec_size_deg': dec_size,
                'wcs_scaled': scaled_wcs,
                'wcs_original': mosaic_wcs
            }
            
        except Exception as e:
            print(f"Error calculating mosaic bounds: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback: try to get pixel scale from WCS and estimate bounds
            try:
                # Get pixel scale from WCS
                pixel_scale = wcs.utils.proj_plane_pixel_scales(mosaic_wcs)  # degrees per pixel
                if len(pixel_scale) >= 2:
                    ra_pixel_scale = pixel_scale[0]  # degrees per pixel in RA
                    dec_pixel_scale = pixel_scale[1]  # degrees per pixel in Dec
                    
                    # Get reference point
                    if 'CRVAL1' in header and 'CRVAL2' in header:
                        center_ra = header['CRVAL1']
                        center_dec = header['CRVAL2']
                    else:
                        center_ra, center_dec = 0.0, 0.0
                    
                    # Calculate approximate size
                    ra_size = naxis1 * ra_pixel_scale
                    dec_size = naxis2 * dec_pixel_scale
                    
                    print(f"Debug: Fallback - pixel scale: RA={ra_pixel_scale:.8f}°/px, Dec={dec_pixel_scale:.8f}°/px")
                    print(f"Debug: Fallback - estimated tile size: RA={ra_size:.6f}°, Dec={dec_size:.6f}°")
                    
                    return {
                        'ra_min': center_ra - ra_size/2,
                        'ra_max': center_ra + ra_size/2,
                        'dec_min': center_dec - dec_size/2,
                        'dec_max': center_dec + dec_size/2,
                        'ra_size_deg': ra_size,
                        'dec_size_deg': dec_size,
                        'wcs_original': mosaic_wcs
                    }
                else:
                    raise ValueError("Could not determine pixel scale")
                    
            except Exception as fallback_error:
                print(f"Fallback calculation also failed: {fallback_error}")
                # Final fallback - use a standard tile size estimate
                return {
                    'ra_min': 0, 'ra_max': 1.0,  # 1 degree tile size
                    'dec_min': 0, 'dec_max': 1.0,
                    'ra_size_deg': 1.0,
                    'dec_size_deg': 1.0,
                    'wcs_original': mosaic_wcs
                }

    def _render_mosaic_to_png(self, processed_image: np.ndarray, bounds: Dict[str, float], 
                             mertileid: int, colormap: str = 'gray') -> str:
        """Render mosaic image to PNG using matplotlib and return as base64 string."""
        cache_key = f"{mertileid}_{colormap}_{processed_image.shape[0]}x{processed_image.shape[1]}"
        
        # Check cache first
        if cache_key in self.png_cache:
            print(f"Debug: Using cached PNG for MER tile {mertileid}")
            return self.png_cache[cache_key]
        
        try:
            print(f"Debug: Rendering PNG for MER tile {mertileid}")
            
            # Create matplotlib figure with no margins
            fig_width = processed_image.shape[1] / self.png_dpi
            fig_height = processed_image.shape[0] / self.png_dpi
            
            fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=self.png_dpi)
            
            # Remove all margins and padding
            fig.subplots_adjust(left=0, bottom=0, right=1, top=1)
            ax.set_position([0, 0, 1, 1])
            
            # Display the image with correct orientation and extent
            extent = [bounds['ra_min'], bounds['ra_max'], bounds['dec_min'], bounds['dec_max']]
            
            # Use imshow with proper extent and origin
            im = ax.imshow(processed_image, 
                          cmap=colormap, 
                          extent=extent,
                          origin='lower',  # Match coordinate system
                          aspect='auto',
                          interpolation='bilinear')
            
            # Remove axes
            ax.set_xticks([])
            ax.set_yticks([])
            ax.axis('off')
            
            # Save to memory buffer as PNG
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.png_dpi, 
                       bbox_inches='tight', pad_inches=0, 
                       facecolor='none', edgecolor='none', transparent=True)
            plt.close(fig)  # Important: close figure to free memory
            
            # Convert to base64
            buf.seek(0)
            img_bytes = buf.getvalue()
            buf.close()
            
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            # Cache the result
            self.png_cache[cache_key] = img_base64
            
            print(f"Debug: Successfully rendered PNG for MER tile {mertileid} ({len(img_base64)//1024} KB)")
            
            return img_base64
            
        except Exception as e:
            print(f"Error rendering PNG for MER tile {mertileid}: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def create_mosaic_image_trace(self, mertileid: int, opacity: float = 0.5, 
                                 colorscale: str = 'gray') -> Optional[go.Image]:
        """Create a Plotly image trace for a mosaic image using pre-rendered PNG."""
        # Load mosaic data for this tile
        mosaic_info = self.get_mosaic_fits_data_by_mertile(mertileid)
        if not mosaic_info:
            print(f"Warning: Could not load mosaic data for MER tile {mertileid}")
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
        
        # Render to PNG
        png_base64 = self._render_mosaic_to_png(processed_image, bounds, mertileid, colorscale)
        if not png_base64:
            print(f"Warning: Failed to render PNG for MER tile {mertileid}")
            return None
        
        # Add debug information about the tile size and coordinates
        print(f"Debug: Creating image trace for MER tile {mertileid}")
        print(f"       - Tile size: {bounds.get('ra_size_deg', 'unknown'):.6f}° × {bounds.get('dec_size_deg', 'unknown'):.6f}°")
        print(f"       - RA range: {bounds['ra_min']:.6f}° to {bounds['ra_max']:.6f}°")
        print(f"       - Dec range: {bounds['dec_min']:.6f}° to {bounds['dec_max']:.6f}°")
        print(f"       - Image shape: {processed_image.shape[0]} × {processed_image.shape[1]} pixels")
        
        # Create the image trace
        trace = go.Image(
            source=f"data:image/png;base64,{png_base64}",
            x0=bounds['ra_min'],
            y0=bounds['dec_min'],
            dx=(bounds['ra_max'] - bounds['ra_min']) / processed_image.shape[1],
            dy=(bounds['dec_max'] - bounds['dec_min']) / processed_image.shape[0],
            opacity=opacity,
            name=f"Mosaic {mertileid}",
            hovertemplate=(
                f"MER Tile: {mertileid}<br>"
                "RA: %{x:.6f}°<br>"
                "Dec: %{y:.6f}°<br>"
                f"Tile Size: {bounds.get('ra_size_deg', 'unknown'):.4f}° × {bounds.get('dec_size_deg', 'unknown'):.4f}°<br>"
                "<extra>Mosaic Image</extra>"
            )
        )
        
        return trace

    def load_mosaic_traces_in_zoom(self, data: Dict[str, Any], relayout_data: Optional[Dict], 
                                  opacity: float = 0.5, colorscale: str = 'gray') -> List[go.Image]:
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
        self.png_cache = {}  # Also clear PNG cache

    def _create_placeholder_trace(self, mertileid: int, opacity: float = 0.5, 
                                 colorscale: str = 'gray') -> go.Image:
        """Create a placeholder trace for large mosaic files that can't be loaded quickly."""
        # Create a small placeholder image
        placeholder_size = 100
        placeholder_data = np.ones((placeholder_size, placeholder_size)) * 0.1
        
        # Render placeholder to PNG
        bounds = {'ra_min': 0, 'ra_max': 1, 'dec_min': 0, 'dec_max': 1}
        
        try:
            png_base64 = self._render_mosaic_to_png(placeholder_data, bounds, mertileid, colorscale)
            
            trace = go.Image(
                source=f"data:image/png;base64,{png_base64}",
                x0=0,
                y0=0,
                dx=0.01,
                dy=0.01,
                opacity=opacity * 0.3,
                name=f"Mosaic {mertileid} (Placeholder)",
                hovertemplate=(
                    f"<b>MER Tile {mertileid}</b><br>"
                    "<i>Mosaic available but not loaded<br>"
                    "(Large file - use async loading)</i><br>"
                    "<extra></extra>"
                )
            )
            
            return trace
            
        except Exception as e:
            print(f"Error creating placeholder for tile {mertileid}: {e}")
            # Return minimal trace if PNG rendering fails
            return go.Scatter(
                x=[0], y=[0], mode='markers', 
                name=f"Mosaic {mertileid} (Error)",
                marker=dict(size=1, opacity=0)
            )

    
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
