"""
Python class to handle the extraction and visualization of mosaic images.
"""

import glob
import os
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import healpy as hp
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objs as go
from astropy import wcs
from astropy.io import fits
from astropy.table import Table
from PIL import Image
from shapely.geometry import box

try:
    from cluster_visualization.src.config import Config
except ImportError:
    raise ImportError("Config module not found in cluster_visualization.src.config")

config = Config()

try:
    from cluster_visualization.src.data.loader import DataLoader
except ImportError:
    raise ImportError("DataLoader module not found in cluster_visualization.src.data.loader")


class MOSAICHandler:
    """Handler for MER mosaic image data, similar to CATREDHandler."""

    def __init__(self, config=None):
        """Initiate MOSAICHandler with performance optimizations"""
        self.traces_cache = {}  # Change to dict for better caching by mertileid
        self.current_mosaic_data = None
        self.config = config if config else Config()

        dataloader = DataLoader(config=self.config)
        paths = dataloader._get_paths(algorithm="PZWAV")
        dataloader._validate_paths(paths)
        self.effcovmask_fileinfo_df = dataloader._load_effcovmask_info(paths)
        self.effcovmask_dsr = self.config.get_effcovmask_dsr() if self.config else None

        self.mosaic_header = None
        self.mosaic_data = None
        self.mosaic_wcs = None

        # Performance-optimized image processing parameters
        self.img_width = 1920  # Reduced from 19200 for faster initial rendering
        self.img_height = 1920  # Reduced from 19200 for faster initial rendering
        self.img_scale_factor = 1 / 10  # Initial downscale factor for performance
        self.n_sigma = 1.0

        # Performance and timeout settings
        self.timeout_minutes = 10  # 10 minute timeout for FITS loading
        self.timeout_seconds = 60 * self.timeout_minutes
        self.max_file_size_gb = 2.0  # Skip files larger than 2GB initially
        self.max_pixels_for_stats = 10_000_000  # Sample large images for statistics

    def get_mosaic_cutout(self, mertileid, racen, deccen, size, mosaicinfo=None):
        """
        Get a cutout from the mosaic FITS file.

        Parameters:
        -----------
        mosaic_fits : str
            Path to the mosaic FITS file.
        racen : float
            Right Ascension of the cutout center (degrees).
        deccen : float
            Declination of the cutout center (degrees).
        size : float
            Size of the cutout (arcmin).
        """

        if mosaicinfo is None:
            try:
                mosaicinfo = self.get_mosaic_fits_data_by_mertile(mertileid)
            except Exception as e:
                print(f"Error loading mosaic data for MER tile {mertileid}: {e}")
                return None, None, None

        mosaic_header = mosaicinfo["header"]
        mosaic_data = mosaicinfo["data"]
        mosaic_wcs = mosaicinfo["wcs"]

        naxis1_org, naxis2_org = mosaic_data.shape[1], mosaic_data.shape[0]  # Original image size
        xcen, ycen = (
            mosaic_wcs.wcs_world2pix(racen, deccen, 0)[0],
            mosaic_wcs.wcs_world2pix(racen, deccen, 0)[1],
        )  # Convert RA/Dec to pixel coordinates

        cdelt = mosaic_wcs.wcs.cd[0][0]  # degrees/pixel - pixel scale
        np0 = int(size / 60 / 2.0 / abs(cdelt))  # Half-width in pixels
        npt = 2 * np0 + 1  # Total cutout size (odd number for center symmetry)

        crpix1, crpix2 = np0 + xcen - int(xcen), np0 + ycen - int(ycen)  # New reference pixel
        crval1, crval2 = (
            mosaic_wcs.wcs_pix2world(xcen, ycen, 0)[0],
            mosaic_wcs.wcs_pix2world(xcen, ycen, 0)[1],
        )  # Reference coordinates

        cutout = np.zeros((npt, npt))

        xmin0, xmax0 = int(xcen) - np0, int(xcen) + np0  # Desired pixel range
        ymin0, ymax0 = int(ycen) - np0, int(ycen) + np0

        xmin, xmax = max(xmin0, 0), min(xmax0, naxis1_org - 1)  # Clamp to image bounds
        ymin, ymax = max(ymin0, 0), min(ymax0, naxis2_org - 1)

        # Copy data, handling cases where cutout extends beyond image edges
        cutout[ymin - ymin0 : npt - (ymax0 - ymax), xmin - xmin0 : npt - (xmax0 - xmax)] = (
            mosaic_data[ymin : ymax + 1, xmin : xmax + 1]
        )

        hdr = mosaicinfo["header"].copy()
        hdr["NAXIS1"] = cutout.shape[1]
        hdr["NAXIS2"] = cutout.shape[0]
        hdr["CRPIX1"] = crpix1
        hdr["CRPIX2"] = crpix2
        hdr["CRVAL1"] = crval1.item()
        hdr["CRVAL2"] = crval2.item()

        wnew = wcs.WCS(hdr)

        # wnew = self.mosaic_wcs.deepcopy()
        # wnew.wcs.crpix[0] = crpix1  # Update reference pixel
        # wnew.wcs.crpix[1] = crpix2
        # wnew.wcs.crval[0] = crval1  # Update reference coordinates
        # wnew.wcs.crval[1] = crval2
        # hdr = wnew.to_header()  # Convert to FITS header
        # naxis1_new, naxis2_new = cutout.shape[1], cutout.shape[0]
        # hdr['NAXIS1'] = naxis1_new
        # hdr['NAXIS2'] = naxis2_new

        return cutout, wnew, hdr

    def get_mosaic_fits_data_by_mertile(self, mertileid):
        """
        Load mosaic FITS data with performance optimization and threading timeout
        """
        # Check if already cached
        if mertileid in self.traces_cache:
            print(f"[CACHE HIT] Using cached data for MER tile {mertileid}")
            return self.traces_cache[mertileid]

        mosaic_dir = self.config.mosaic_dir
        try:
            fits_files = glob.glob(
                os.path.join(mosaic_dir, f"EUC_MER_BGSUB-MOSAIC-VIS_TILE{mertileid}*.fits.gz")
            )
        except:
            print(f"Error accessing directory {mosaic_dir}, trying subdirectories...")
            for subdir in os.listdir(mosaic_dir):
                subdir_path = os.path.join(mosaic_dir, subdir)
                if os.path.isdir(subdir_path):
                    fits_files = glob.glob(
                        os.path.join(
                            subdir_path, f"EUC_MER_BGSUB-MOSAIC-VIS_TILE{mertileid}*.fits.gz"
                        )
                    )
                    if fits_files:
                        break

        if not fits_files:
            print(f"Warning: No mosaic FITS file found for MER tile {mertileid}")
            return None

        fits_file = fits_files[0]  # Take the first match
        file_size_gb = os.path.getsize(fits_file) / (1024**3)

        # Check file size for initial performance optimization
        if file_size_gb > self.max_file_size_gb:
            print(f"[WARNING] Large file ({file_size_gb:.2f}GB) - may take longer to process")

        print(f"[LOADING] Processing mosaic for MER tile {mertileid} ({file_size_gb:.2f}GB)...")

        # Thread-safe FITS loading with timeout
        result_queue = queue.Queue()
        error_queue = queue.Queue()

        def load_fits_with_timeout():
            try:
                start_time = time.time()

                # Use memmap=False to avoid memory mapping issues with compressed files
                with fits.open(
                    fits_file, mode="readonly", ignore_missing_simple=True, memmap=False
                ) as hdul:
                    primary_hdu = hdul[0]
                    header = primary_hdu.header.copy()
                    # Create a copy of the data to avoid issues with file closure
                    data = primary_hdu.data.copy() if primary_hdu.data is not None else None
                    wcs_obj = wcs.WCS(primary_hdu.header)

                    if data is None:
                        error_queue.put(f"No data in primary HDU for {fits_file}")
                        return

                    load_time = time.time() - start_time
                    print(f"[TIMING] FITS loaded in {load_time:.2f}s")

                    result_queue.put(
                        {"header": header, "data": data, "wcs": wcs_obj, "file_path": fits_file}
                    )

            except Exception as e:
                error_queue.put(str(e))

        # Start loading thread
        load_thread = threading.Thread(target=load_fits_with_timeout)
        load_thread.daemon = True
        load_thread.start()

        # Wait with timeout
        load_thread.join(timeout=self.timeout_seconds)

        if load_thread.is_alive():
            print(f"[TIMEOUT] Loading MER tile {mertileid} timed out after {self.timeout_seconds}s")
            return None

        # Check for errors
        if not error_queue.empty():
            error_msg = error_queue.get()
            print(f"[ERROR] Failed to load MER tile {mertileid}: {error_msg}")
            return None

        # Get results
        if result_queue.empty():
            print(f"[ERROR] No data loaded for MER tile {mertileid}")
            return None

        result = result_queue.get()

        # Store in instance variables for compatibility
        self.mosaic_header = result["header"]
        self.mosaic_data = result["data"]
        self.mosaic_wcs = result["wcs"]

        # Cache results
        self.traces_cache[mertileid] = result

        print(f"[SUCCESS] Processed MER tile {mertileid}")

        return result

    def _extract_zoom_ranges(
        self, relayout_data: Dict
    ) -> Optional[Tuple[float, float, float, float]]:
        """Extract zoom ranges from Plotly relayout data."""
        ra_min = ra_max = dec_min = dec_max = None

        # Extract RA range
        if "xaxis.range[0]" in relayout_data and "xaxis.range[1]" in relayout_data:
            ra_min = relayout_data["xaxis.range[0]"]
            ra_max = relayout_data["xaxis.range[1]"]
        elif "xaxis.range" in relayout_data:
            ra_min = relayout_data["xaxis.range"][0]
            ra_max = relayout_data["xaxis.range"][1]

        # Extract Dec range
        if "yaxis.range[0]" in relayout_data and "yaxis.range[1]" in relayout_data:
            dec_min = relayout_data["yaxis.range[0]"]
            dec_max = relayout_data["yaxis.range[1]"]
        elif "yaxis.range" in relayout_data:
            dec_min = relayout_data["yaxis.range"][0]
            dec_max = relayout_data["yaxis.range"][1]

        if all(v is not None for v in [ra_min, ra_max, dec_min, dec_max]):
            return (ra_min, ra_max, dec_min, dec_max)
        return None

    def _find_intersecting_tiles(
        self, data: Dict[str, Any], ra_min: float, ra_max: float, dec_min: float, dec_max: float
    ) -> List[int]:
        """Find MER tiles whose polygons intersect with the zoom box."""
        zoom_box = box(ra_min, dec_min, ra_max, dec_max)
        mertiles_to_load = []

        # Check if catred_info exists in data (contains tile polygons)
        if "catred_info" not in data:
            print("Warning: No catred_info found in data for tile intersection")
            return mertiles_to_load

        for uid, row in (
            data["catred_info"]
            .loc[data["catred_info"]["dataset_release"] == data.get("catred_dsr", None)]
            .iterrows()
        ):
            mertileid = row["mertileid"]
            poly = row["polygon"]
            if poly is not None:
                # Use proper geometric intersection
                if poly.intersects(zoom_box):
                    mertiles_to_load.append(mertileid)

        print(
            f"Debug: Found {len(mertiles_to_load)} MER tiles with mosaics in zoom area: "
            f"{mertiles_to_load[:5]}{'...' if len(mertiles_to_load) > 5 else ''}"
        )

        return mertiles_to_load

    def _process_mosaic_image(
        self,
        mosaic_data: np.ndarray,
        target_width_and_height: Union[list, tuple] = None,
        target_scale_factor: float = None,
    ) -> np.ndarray:
        """
        Process mosaic image data with early downsampling for performance optimization
        """
        if target_width_and_height is None and target_scale_factor is None:
            print(
                "Warning: No target dimensions or scale factor provided for mosaic processing, using original size"
            )
            target_width = mosaic_data.shape[1]
            target_height = mosaic_data.shape[0]
        elif target_width_and_height is None and target_scale_factor is not None:
            target_width = int(mosaic_data.shape[1] * target_scale_factor)
            target_height = int(mosaic_data.shape[0] * target_scale_factor)
        elif target_width_and_height is not None:
            assert (
                len(target_width_and_height) == 2
            ), "target_width_and_height must be a tuple/list of (width, height)"
            target_width, target_height = target_width_and_height

        self.img_width = target_width
        self.img_height = target_height

        try:
            # Ensure we have a valid numpy array
            if not isinstance(mosaic_data, np.ndarray):
                print(f"Warning: mosaic_data is not ndarray, type: {type(mosaic_data)}")
                return np.zeros((target_height, target_width))

            print(
                f"Debug: Original mosaic dimensions: {mosaic_data.shape[1]} x {mosaic_data.shape[0]} pixels"
            )
            print(f"Debug: Target dimensions: {target_width} x {target_height} pixels")

            # PERFORMANCE OPTIMIZATION: Early downsampling for very large images
            original_shape = mosaic_data.shape
            downsample_factor = 1

            # If image is more than 4x larger than target, downsample first
            if original_shape[0] > target_height * 4 or original_shape[1] > target_width * 4:
                downsample_factor = max(
                    original_shape[0] // (target_height * 2),
                    original_shape[1] // (target_width * 2),
                )
                if downsample_factor > 1:
                    print(
                        f"Debug: Early downsampling by factor {downsample_factor} for performance"
                    )
                    mosaic_data = mosaic_data[::downsample_factor, ::downsample_factor]
                    print(
                        f"Debug: Downsampled to: {mosaic_data.shape[1]} x {mosaic_data.shape[0]} pixels"
                    )

            # Handle NaN values - similar to notebook approach
            valid_mask = np.isfinite(mosaic_data)
            if not np.any(valid_mask):
                print("Warning: No valid data found in mosaic image")
                return np.zeros((target_height, target_width))

            print("Debug: Computing statistics...")

            # Apply sigma clipping and normalization
            # Use ravel to flatten the array for mean and std calculations
            # For large arrays, sample a subset for statistics to speed up processing
            # if mosaic_data.size > self.max_pixels_for_stats:  # If larger than 10M pixels
            #     print("Debug: Large image detected, sampling for statistics...")
            #     # Sample every 10th pixel for statistics
            #     sample_data = mosaic_data[::10, ::10].ravel()
            #     mean = np.mean(sample_data)
            #     std = np.std(sample_data)
            # else:
            #     # Sample all pixels for statistics
            #     mean = np.mean(mosaic_data.ravel())
            #     std = np.std(mosaic_data.ravel())

            mean = np.mean(mosaic_data.ravel())
            std = np.std(mosaic_data.ravel())

            print(f"Debug: Mosaic data statistics - mean: {mean:.3f}, std: {std:.3f}")

            # Clip the data to the range [0, mean + N * std] where N = n_sigma
            max_val = mean + self.n_sigma * std
            print(f"Debug: Clipping data to range [0, {max_val:.3f}]")

            mer_image = np.clip(mosaic_data, 0.0, max_val)

            # Normalize the image
            mer_image = mer_image / max_val

            print(
                f"Debug: After clipping and normalization - range: [{np.min(mer_image):.3f}, {np.max(mer_image):.3f}]"
            )

            print("Debug: Starting image resize...")

            # Resize the image to match target dimensions
            # Convert to PIL Image, resize with LANCZOS,
            # and transpose with FLIP_LEFT_RIGHT
            mer_array = np.array(
                Image.fromarray(mer_image)
                .resize((target_width, target_height), Image.Resampling.LANCZOS)
                .transpose(Image.FLIP_LEFT_RIGHT)
            )

            print(f"Debug: Final processed image shape: {mer_array.shape}")

            # Clean up large arrays to free memory
            del mer_image
            if "sample_data" in locals():
                del sample_data

            return mer_array

        except Exception as e:
            print(f"Error processing mosaic image: {e}")
            import traceback

            traceback.print_exc()
            return np.zeros((target_height, target_width))

    def _create_scaled_wcs(
        self,
        original_header: fits.Header,
        original_shape: Tuple[int, int],
        target_width: int,
        target_height: int,
    ) -> wcs.WCS:
        """Create a scaled WCS header similar to the notebook's header_binned approach."""
        try:
            # Calculate scaling factors based on the original and target dimensions
            orig_height, orig_width = original_shape
            scale_x = orig_width / target_width
            scale_y = orig_height / target_height

            print(f"Debug: WCS scaling factors - scale_x: {scale_x:.3f}, scale_y: {scale_y:.3f}")

            # Create a modified header (binned header) similar to notebook
            header_binned = original_header.copy()
            header_binned["NAXIS1"] = target_width
            header_binned["NAXIS2"] = target_height

            # Adjust WCS parameters for the scaling
            if "CRPIX1" in header_binned:
                header_binned["CRPIX1"] = header_binned["CRPIX1"] / scale_x
            if "CRPIX2" in header_binned:
                header_binned["CRPIX2"] = header_binned["CRPIX2"] / scale_y

            # Scale the CD matrix elements
            if "CD1_1" in header_binned:
                header_binned["CD1_1"] = header_binned["CD1_1"] * scale_x
            if "CD1_2" in header_binned:
                header_binned["CD1_2"] = header_binned["CD1_2"] * scale_x
            if "CD2_1" in header_binned:
                header_binned["CD2_1"] = header_binned["CD2_1"] * scale_y
            if "CD2_2" in header_binned:
                header_binned["CD2_2"] = header_binned["CD2_2"] * scale_y

            # Alternative: if using CDELT instead of CD matrix
            if "CDELT1" in header_binned and "CD1_1" not in header_binned:
                header_binned["CDELT1"] = header_binned["CDELT1"] * scale_x
            if "CDELT2" in header_binned and "CD2_2" not in header_binned:
                header_binned["CDELT2"] = header_binned["CDELT2"] * scale_y

            # Create the scaled WCS
            wcs_binned = wcs.WCS(header_binned)

            print(f"Debug: Created scaled WCS for {target_width}x{target_height} image")

            return wcs_binned

        except Exception as e:
            print(f"Warning: Failed to create scaled WCS, using original: {e}")
            # Fallback to original WCS
            return wcs.WCS(original_header)

    def _calculate_image_bounds(
        self,
        mosaic_wcs: wcs.WCS,
        header: fits.Header,
        target_width: int,
        target_height: int,
        wcs_cutout=None,
    ) -> Dict[str, float]:
        """Calculate coordinate bounds for the processed image using scaled WCS approach from notebook."""
        try:
            if wcs_cutout:
                print("Debug: Using provided wcs_cutout for bounds calculation")
                scaled_wcs = wcs_cutout
            else:
                # Get the original image dimensions
                naxis1 = header["NAXIS1"]  # Width in pixels
                naxis2 = header["NAXIS2"]  # Height in pixels
                print(f"Debug: Original mosaic dimensions: {naxis1} x {naxis2} pixels")
                # Create scaled WCS similar to notebook's header_binned approach
                original_shape = (naxis2, naxis1)  # (height, width)
                scaled_wcs = self._create_scaled_wcs(
                    header, original_shape, target_width, target_height
                )

            # Define corner pixels of the SCALED/BINNED image
            corners_pix = np.array(
                [
                    [0.5, 0.5],  # Bottom-left
                    [target_width + 0.5, 0.5],  # Bottom-right
                    [target_width + 0.5, target_height + 0.5],  # Top-right
                    [0.5, target_height + 0.5],  # Top-left
                ]
            )

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
                    print(
                        f"Debug: Adjusted RA bounds: ({ra_min:.6f}, {ra_max:.6f}) = {ra_size:.6f}°"
                    )

            return {
                "ra_min": ra_min,
                "ra_max": ra_max,
                "dec_min": dec_min,
                "dec_max": dec_max,
                "ra_size_deg": ra_size,
                "dec_size_deg": dec_size,
                "wcs_scaled": scaled_wcs,
                "wcs_original": mosaic_wcs,
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
                    if "CRVAL1" in header and "CRVAL2" in header:
                        center_ra = header["CRVAL1"]
                        center_dec = header["CRVAL2"]
                    else:
                        center_ra, center_dec = 0.0, 0.0

                    # Calculate approximate size
                    ra_size = naxis1 * ra_pixel_scale
                    dec_size = naxis2 * dec_pixel_scale

                    print(
                        f"Debug: Fallback - pixel scale: RA={ra_pixel_scale:.8f}°/px, Dec={dec_pixel_scale:.8f}°/px"
                    )
                    print(
                        f"Debug: Fallback - estimated tile size: RA={ra_size:.6f}°, Dec={dec_size:.6f}°"
                    )

                    return {
                        "ra_min": center_ra - ra_size / 2,
                        "ra_max": center_ra + ra_size / 2,
                        "dec_min": center_dec - dec_size / 2,
                        "dec_max": center_dec + dec_size / 2,
                        "ra_size_deg": ra_size,
                        "dec_size_deg": dec_size,
                        "wcs_original": mosaic_wcs,
                    }
                else:
                    raise ValueError("Could not determine pixel scale")

            except Exception as fallback_error:
                print(f"Fallback calculation also failed: {fallback_error}")
                # Final fallback - use a standard tile size estimate
                return {
                    "ra_min": 0,
                    "ra_max": 1.0,  # 1 degree tile size
                    "dec_min": 0,
                    "dec_max": 1.0,
                    "ra_size_deg": 1.0,
                    "dec_size_deg": 1.0,
                    "wcs_original": mosaic_wcs,
                }

    def _calculate_image_bounds_direct(
        self, mosaic_wcs: wcs.WCS, processed_image: np.ndarray
    ) -> Dict[str, float]:
        """Calculate bounds using original WCS and image corners."""
        height, width = processed_image.shape

        # Define corner pixels of the PROCESSED image
        corners = np.array(
            [
                [0, 0],  # Bottom-left
                [width - 1, 0],  # Bottom-right
                [width - 1, height - 1],  # Top-right
                [0, height - 1],  # Top-left
            ]
        )

        # FIXED: Get the original image dimensions from WCS header
        try:
            # Get original dimensions from the WCS object
            if hasattr(mosaic_wcs, "_naxis"):
                orig_width = mosaic_wcs._naxis[0]
                orig_height = mosaic_wcs._naxis[1]
            elif hasattr(mosaic_wcs, "pixel_shape"):
                orig_height, orig_width = mosaic_wcs.pixel_shape
            else:
                # Fallback: get from the stored mosaic data
                orig_height, orig_width = self.mosaic_data.shape

            print(f"Debug: Original image size: {orig_width} x {orig_height}")
            print(f"Debug: Processed image size: {width} x {height}")

            # Calculate correct scaling factors
            scale_x = orig_width / width
            scale_y = orig_height / height

            print(f"Debug: Scale factors: scale_x={scale_x:.3f}, scale_y={scale_y:.3f}")

            # Scale corners back to original image coordinates
            corners_original = corners * [scale_x, scale_y]

            # Convert to world coordinates using original WCS
            ra_coords, dec_coords = mosaic_wcs.wcs_pix2world(
                corners_original[:, 0], corners_original[:, 1], 0
            )

        except Exception as e:
            print(f"Warning: Could not get original dimensions, using direct conversion: {e}")
            # Fallback: use processed image corners directly with WCS
            # This assumes the WCS has been properly scaled for the processed image
            ra_coords, dec_coords = mosaic_wcs.wcs_pix2world(corners[:, 0], corners[:, 1], 0)

        ra_size = np.max(ra_coords) - np.min(ra_coords)
        dec_size = np.max(dec_coords) - np.min(dec_coords)

        return {
            "ra_min": np.min(ra_coords),
            "ra_max": np.max(ra_coords),
            "dec_min": np.min(dec_coords),
            "dec_max": np.max(dec_coords),
            "ra_size_deg": ra_size,
            "dec_size_deg": dec_size,
        }

    def _create_mask_colorbar_trace(
        self,
        weight_min: float,
        weight_max: float,
        colorscale: str = "viridis",
        title: str = "Weight",
    ) -> go.Heatmap:
        """
        Create an invisible heatmap trace that only displays a colorbar for mask overlays.

        This trace provides a visual reference for the weight values of HEALPix mask pixels
        without adding any visible data to the plot.
        """
        # Create a minimal 2x2 array with the weight range
        z_colorbar = np.array([[weight_min, weight_max], [weight_min, weight_max]])

        # Create the colorbar trace
        # Use visible='legendonly' to prevent the dummy coordinates from affecting axis ranges
        colorbar_trace = go.Heatmap(
            z=z_colorbar,
            x=[0, 1],  # Minimal coordinates (won't affect plot range)
            y=[0, 1],
            colorscale=colorscale,
            showscale=True,  # Show the colorbar
            visible="legendonly",  # Hide from plot but show colorbar
            hoverinfo="skip",  # Don't show hover info for this trace
            showlegend=False,
            name="Mask Colorbar",
            colorbar=dict(
                title=dict(text=title, side="right", font=dict(size=12)),
                thickness=15,
                len=0.5,  # 50% of plot height
                x=1.02,  # Position slightly to the right of the plot
                xanchor="left",
                y=0.5,  # Center vertically
                yanchor="middle",
                tickmode="linear",
                tick0=weight_min,
                dtick=(weight_max - weight_min) / 5,  # 5 ticks
                tickfont=dict(size=10),
                outlinewidth=1,
                outlinecolor="gray",
            ),
        )

        return colorbar_trace

    def create_mosaic_image_trace(
        self, mertileid: int, opacity: float = 0.5, colorscale: str = "gray"
    ) -> Optional[go.Heatmap]:
        """Create a Plotly heatmap trace for a mosaic image."""
        # Load mosaic data for this tile
        mosaic_info = self.get_mosaic_fits_data_by_mertile(mertileid)
        if not mosaic_info:
            print(f"Warning: Could not load mosaic data for MER tile {mertileid}")
            return None

        # Process the image
        processed_image = self._process_mosaic_image(
            mosaic_info["data"], target_scale_factor=self.img_scale_factor
        )

        # Calculate coordinate bounds
        # bounds = self._calculate_image_bounds(
        #     mosaic_info['wcs'],
        #     mosaic_info['header'],
        #     self.img_width,
        #     self.img_height
        # )
        bounds = self._calculate_image_bounds_direct(mosaic_info["wcs"], processed_image)

        # Create coordinate arrays for the heatmap
        height, width = processed_image.shape
        x_coords = np.linspace(bounds["ra_min"], bounds["ra_max"], width)
        y_coords = np.linspace(bounds["dec_min"], bounds["dec_max"], height)

        # Add debug information about the tile size and coordinates
        print(f"Debug: Creating heatmap trace for MER tile {mertileid}")
        print(
            f"       - Tile size: {bounds.get('ra_size_deg', 'unknown'):.6f}° × {bounds.get('dec_size_deg', 'unknown'):.6f}°"
        )
        print(f"       - RA range: {bounds['ra_min']:.6f}° to {bounds['ra_max']:.6f}°")
        print(f"       - Dec range: {bounds['dec_min']:.6f}° to {bounds['dec_max']:.6f}°")
        print(f"       - Image shape: {height} × {width} pixels")

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
                "RA: %{x:.6f}°<br>"
                "Dec: %{y:.6f}°<br>"
                "Intensity: %{z:.3f}<br>"
                f"Tile Size: {bounds.get('ra_size_deg', 'unknown'):.4f}° × {bounds.get('dec_size_deg', 'unknown'):.4f}°<br>"
                "<extra>Mosaic Image</extra>"
            ),
        )

        return trace

    def create_mask_overlay_trace(
        self,
        mertileid: int,
        opacity: float = 0.6,
        colorscale: str = "viridis",
        add_colorbar: bool = True,
    ) -> Optional[go.Heatmap]:
        """Create a Plotly heatmap trace for a mask overlay."""

        # Load mosaic data for this tile
        mosaic_info = self.get_mosaic_fits_data_by_mertile(mertileid)
        if not mosaic_info:
            print(f"Warning: Could not load mosaic data for MER tile {mertileid}")
            return None
        mosaic_data = mosaic_info["data"]
        wcs_mosaic = mosaic_info["wcs"]

        # Get the full mosaic WCS and shape
        print(f"Full mask overlay array shape: {mosaic_data.shape}")
        # print(f"Full mosaic WCS: {wcs_mosaic}")

        # Get RA/Dec limits from the full mosaic
        ny, nx = mosaic_data.shape
        corners = wcs_mosaic.pixel_to_world([0, nx - 1, nx - 1, 0], [0, 0, ny - 1, ny - 1])
        ra_min_mosaic, ra_max_mosaic = corners.ra.deg.min(), corners.ra.deg.max()
        dec_min_mosaic, dec_max_mosaic = corners.dec.deg.min(), corners.dec.deg.max()

        print(f"RA range: {ra_min_mosaic:.4f} to {ra_max_mosaic:.4f}")
        print(f"Dec range: {dec_min_mosaic:.4f} to {dec_max_mosaic:.4f}")

        # Load the effective coverage mask for this MER tile
        hpmask_fits = self.effcovmask_fileinfo_df.loc[
            (self.effcovmask_fileinfo_df["mertileid"] == mertileid)
            & (self.effcovmask_fileinfo_df["dataset_release"] == self.effcovmask_dsr)
        ].squeeze()["fits_file"]
        footprint = Table.read(hpmask_fits, format="fits", hdu=1)
        print(f"Loaded HEALPix footprint with {len(footprint)} pixels from {hpmask_fits}")
        footprint["ra"], footprint["dec"] = hp.pix2ang(
            nside=16384, ipix=footprint["PIXEL"], nest=True, lonlat=True
        )

        # Filter footprint pixels to the full MER tile region
        _pix_mask = (
            (footprint["WEIGHT"] > 0)
            & (footprint["ra"] >= ra_min_mosaic - 0.01)
            & (footprint["ra"] <= ra_max_mosaic + 0.01)
            & (footprint["dec"] >= dec_min_mosaic - 0.01)
            & (footprint["dec"] <= dec_max_mosaic + 0.01)
        )

        print(f"Footprint pixels in full mosaic: {_pix_mask.sum()}")
        if _pix_mask.sum() > 0:
            print(
                f"Weight range: {footprint['WEIGHT'][_pix_mask].min():.3f} to {footprint['WEIGHT'][_pix_mask].max():.3f}"
            )

        # Create traces for HEALPix footprint polygons
        footprint_traces = []
        weight_min, weight_max = 0.8, 1.0

        if _pix_mask.sum() > 0:
            print(f"Creating {_pix_mask.sum()} HEALPix polygon traces...")

            for idx, (pix, weight) in enumerate(
                zip(footprint["PIXEL"][_pix_mask], footprint["WEIGHT"][_pix_mask])
            ):
                # Get pixel boundaries
                rapix, decpix = self.get_healpix_boundaries(
                    pix, nside=16384, nest=True, step=2, mertileid=mertileid, wcs_mosaic=wcs_mosaic
                )
                rapix = np.append(rapix, rapix[0])  # Close the polygon
                decpix = np.append(decpix, decpix[0])  # Close the polygon

                ra, dec = wcs_mosaic.wcs_pix2world(rapix, decpix, 0)

                # Normalize weight for colorscale
                weight_norm = (weight - weight_min) / (weight_max - weight_min)
                try:
                    colormap = getattr(plt.cm, colorscale)
                    color = colormap(weight_norm)  # RGBA
                except AttributeError:
                    print(f"Warning: Invalid colorscale '{colorscale}', defaulting to 'viridis'")
                    colormap = plt.cm.viridis
                    color = colormap(weight_norm)

                footprint_traces.append(
                    go.Scatter(
                        x=list(ra),
                        y=list(dec),
                        mode="lines",
                        fill="toself",
                        fillcolor=f"rgba({int(color[0]*255)},{int(color[1]*255)},{int(color[2]*255)},{opacity})",
                        line=dict(width=0.5, color="yellow"),
                        name=f"Mask overlay pixel {pix}",
                        showlegend=False,
                        hovertext=f"HEALPix {pix}<br>Weight: {weight:.3f}",
                        hoverinfo="text",
                        customdata=[[weight]],
                    )
                )

        # Add a colorbar trace (invisible heatmap that only shows the colorbar)
        if footprint_traces and add_colorbar:
            colorbar_trace = self._create_mask_colorbar_trace(
                weight_min, weight_max, colorscale, title="Coverage<br>Weight"
            )
            footprint_traces.append(colorbar_trace)

        return footprint_traces

    def create_mosaic_cutout_trace(
        self,
        data: Dict[str, Any],
        clickdata: Dict[str, Any],
        opacity: float = 1,
        colorscale: str = "viridis",
    ) -> Optional[go.Heatmap]:
        """Create a Plotly heatmap trace for a mosaic cutout."""

        print(f"Debug: Creating cutout trace with size {clickdata.get('cutout_size', 1)} arcmin")

        ra_cen, dec_cen = clickdata["cluster_ra"], clickdata["cluster_dec"]

        ra_min, ra_max = ra_cen - 1e-4, ra_cen + 1e-4  # Small box around click
        dec_min, dec_max = dec_cen - 1e-4, dec_cen + 1e-4  # Small box around click

        # Find which MER tiles intersect with the cutout region
        mertiles_to_load = self._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)
        if len(mertiles_to_load) != 1:
            print("Warning: Multiple MER tiles intersect with cutout region, returning None")
            return None
        else:
            mertileid = mertiles_to_load[0]

        mosaicinfo = self.get_mosaic_fits_data_by_mertile(mertileid)

        # Load mosaic data for this tile
        try:
            data_cutout, wcs_cutout, hdr_cutout = self.get_mosaic_cutout(
                mertileid=mertileid,
                racen=ra_cen,
                deccen=dec_cen,
                size=clickdata.get("cutout_size", 1),  # size in arcmin
                mosaicinfo=mosaicinfo,
            )
        except Exception as e:
            print(f"Warning: Exception while getting cutout for MER tile {mertileid}: {e}")
            return None

        # Process the image
        if data_cutout is None:
            print(f"Warning: Could not get cutout for MER tile {mertileid}")
            return None
        else:
            processed_image = self._process_mosaic_image(data_cutout)

        # Calculate coordinate bounds
        # bounds = self._calculate_image_bounds(
        #     mosaicinfo['wcs'],
        #     hdr_cutout,
        #     self.img_width,
        #     self.img_height,
        #     wcs_cutout=wcs_cutout
        # )

        bounds = self._calculate_image_bounds_direct(wcs_cutout, processed_image)

        # Create coordinate arrays for the heatmap
        height, width = processed_image.shape
        x_coords = np.linspace(bounds["ra_min"], bounds["ra_max"], width)
        y_coords = np.linspace(bounds["dec_min"], bounds["dec_max"], height)

        # Add debug information about the tile size and coordinates
        print(f"Debug: Creating heatmap trace for MER tile {mertileid}")
        print(
            f"       - Tile size (degree): {bounds.get('ra_size_deg', 'unknown'):.6f}° × {bounds.get('dec_size_deg', 'unknown'):.6f}°"
        )
        print(
            f"       - Tile size (arcmin): {bounds.get('ra_size_deg', 'unknown')*60:.3f} arcmin × {bounds.get('dec_size_deg', 'unknown')*60:.3f} arcmin"
        )
        print(f"       - RA range: {bounds['ra_min']:.6f}° to {bounds['ra_max']:.6f}°")
        print(f"       - Dec range: {bounds['dec_min']:.6f}° to {bounds['dec_max']:.6f}°")
        print(f"       - Image shape: {height} × {width} pixels")

        # Create the heatmap trace
        trace = go.Heatmap(
            z=processed_image,
            x=x_coords,
            y=y_coords,
            opacity=opacity,
            colorscale=colorscale,
            showscale=False,  # Don't show colorbar
            name=f"MER-Mosaic cutout #{clickdata.get('nclicks', 1)}",
            hovertemplate=(
                f"MER Tile: {mertileid}<br>"
                "RA: %{x:.6f}°<br>"
                "Dec: %{y:.6f}°<br>"
                "Intensity: %{z:.3f}<br>"
                f"Tile Size: {bounds.get('ra_size_deg', 'unknown'):.4f}° × {bounds.get('dec_size_deg', 'unknown'):.4f}°<br>"
                "<extra>Mosaic Image</extra>"
            ),
        )

        return trace

    def create_mask_overlay_cutout_trace(
        self,
        data: Dict[str, Any],
        clickdata: Dict[str, Any],
        opacity: float = 0.6,
        colorscale: str = "viridis",
        add_colorbar: bool = True,
    ) -> List[go.Scatter]:
        """Create Plotly scatter traces for a mask overlay cutout."""

        ra_cen, dec_cen = clickdata["cluster_ra"], clickdata["cluster_dec"]

        ra_min, ra_max = ra_cen - 1e-4, ra_cen + 1e-4  # Small box around click
        dec_min, dec_max = dec_cen - 1e-4, dec_cen + 1e-4  # Small box around click

        # Find which MER tiles intersect with the cutout region
        mertiles_to_load = self._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)
        if len(mertiles_to_load) != 1:
            print("Warning: Multiple MER tiles intersect with cutout region, returning empty list")
            return []
        else:
            mertileid = mertiles_to_load[0]

        # Load mosaic data for this tile
        try:
            data_cutout, wcs_cutout, hdr_cutout = self.get_mosaic_cutout(
                mertileid=mertileid,
                racen=ra_cen,
                deccen=dec_cen,
                size=clickdata.get("mask_cutout_size", 1),  # size in arcmin
            )
        except Exception as e:
            print(f"Warning: Exception while getting cutout for MER tile {mertileid}: {e}")
            return None

        if data_cutout is None:
            print(f"Warning: Could not get cutout for MER tile {mertileid}")
            print("Returning full mask overlay traces instead")
            # Create mask overlay traces for full tile instead
            mask_traces = self.create_mask_overlay_trace(mertileid=mertileid, opacity=opacity)
            return mask_traces

        # Get the full mosaic WCS and shape
        print(f"Full mask overlay array shape: {data_cutout.shape}")
        # print(f"Full mosaic WCS: {wcs_mosaic}")

        # Get RA/Dec limits from the full mosaic
        ny, nx = data_cutout.shape
        corners = wcs_cutout.pixel_to_world([0, nx - 1, nx - 1, 0], [0, 0, ny - 1, ny - 1])
        ra_min_mosaic, ra_max_mosaic = corners.ra.deg.min(), corners.ra.deg.max()
        dec_min_mosaic, dec_max_mosaic = corners.dec.deg.min(), corners.dec.deg.max()

        print(f"RA range: {ra_min_mosaic:.4f} to {ra_max_mosaic:.4f}")
        print(f"Dec range: {dec_min_mosaic:.4f} to {dec_max_mosaic:.4f}")

        # Load the effective coverage mask for this MER tile
        hpmask_fits = self.effcovmask_fileinfo_df.loc[
            (self.effcovmask_fileinfo_df["mertileid"] == mertileid)
            & (self.effcovmask_fileinfo_df["dataset_release"] == self.effcovmask_dsr)
        ].squeeze()["fits_file"]
        footprint = Table.read(hpmask_fits, format="fits", hdu=1)
        print(f"Loaded HEALPix footprint with {len(footprint)} pixels from {hpmask_fits}")
        footprint["ra"], footprint["dec"] = hp.pix2ang(
            nside=16384, ipix=footprint["PIXEL"], nest=True, lonlat=True
        )

        # Filter footprint pixels to the full MER tile region
        _pix_mask = (
            (footprint["WEIGHT"] > 0)
            & (footprint["ra"] >= ra_min_mosaic - 0.01)
            & (footprint["ra"] <= ra_max_mosaic + 0.01)
            & (footprint["dec"] >= dec_min_mosaic - 0.01)
            & (footprint["dec"] <= dec_max_mosaic + 0.01)
        )

        print(f"Footprint pixels in selected (mosaic) area: {_pix_mask.sum()}")
        if _pix_mask.sum() > 0:
            print(
                f"Weight range: {footprint['WEIGHT'][_pix_mask].min():.3f} to {footprint['WEIGHT'][_pix_mask].max():.3f}"
            )

        # Create traces for HEALPix footprint polygons
        footprint_traces = []
        weight_min, weight_max = 0.8, 1.0

        if _pix_mask.sum() > 0:
            print(f"Creating {_pix_mask.sum()} HEALPix polygon traces...")

            for idx, (pix, weight) in enumerate(
                zip(footprint["PIXEL"][_pix_mask], footprint["WEIGHT"][_pix_mask])
            ):
                # Get pixel boundaries
                rapix, decpix = self.get_healpix_boundaries(
                    pix, nside=16384, nest=True, step=2, mertileid=mertileid, wcs_mosaic=wcs_cutout
                )

                ra, dec = wcs_cutout.wcs_pix2world(rapix, decpix, 0)

                # Close the polygon
                ra = np.append(ra, ra[0])
                dec = np.append(dec, dec[0])

                # Normalize weight for colorscale
                weight_norm = (weight - weight_min) / (weight_max - weight_min)
                try:
                    colormap = getattr(plt.cm, colorscale)
                    color = colormap(weight_norm)  # RGBA
                except AttributeError:
                    print(f"Warning: Invalid colorscale '{colorscale}', defaulting to 'viridis'")
                    colormap = plt.cm.viridis
                    color = colormap(weight_norm)

                footprint_traces.append(
                    go.Scatter(
                        x=list(ra),
                        y=list(dec),
                        mode="lines",
                        fill="toself",
                        fillcolor=f"rgba({int(color[0]*255)},{int(color[1]*255)},{int(color[2]*255)},{opacity})",
                        line=dict(width=0.5, color="yellow"),
                        name=f"Mask overlay (cutout) pixel {pix}",
                        showlegend=False,
                        hovertext=f"HEALPix {pix}<br>Weight: {weight:.3f}",
                        hoverinfo="text",
                        customdata=[[weight]],
                    )
                )

        # Add a colorbar trace (invisible heatmap that only shows the colorbar)
        if footprint_traces and add_colorbar:
            colorbar_trace = self._create_mask_colorbar_trace(
                weight_min, weight_max, colorscale, title="Coverage<br>Weight"
            )
            footprint_traces.append(colorbar_trace)

        return footprint_traces

    def load_mosaic_traces_in_zoom(
        self,
        data: Dict[str, Any],
        relayout_data: Optional[Dict],
        opacity: float = 0.5,
        colorscale: str = "gray",
    ) -> List[go.Heatmap]:
        """
        Load mosaic image traces with strict performance limits and timing
        """
        start_time = time.time()
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
        print(
            f"Debug: Loading mosaics for zoom area: RA({ra_min:.3f}, {ra_max:.3f}), "
            f"Dec({dec_min:.3f}, {dec_max:.3f})"
        )

        # Find intersecting tiles
        mertiles_to_load = self._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)

        if not mertiles_to_load:
            print("Debug: No MER tiles with mosaics found in zoom area")
            return traces

        # PERFORMANCE LIMITS: Strict limits for interactive experience
        max_mosaics = 5  # Maximum 5 mosaics per zoom
        max_processing_time = 30  # Maximum 30 seconds total processing time

        if len(mertiles_to_load) > max_mosaics:
            print(f"Debug: Limiting to first {max_mosaics} mosaics for performance")
            mertiles_to_load = mertiles_to_load[:max_mosaics]

        # Create traces for each mosaic with timing checks
        for i, mertileid in enumerate(mertiles_to_load):
            # Check if we're running out of time
            elapsed_time = time.time() - start_time
            if elapsed_time > max_processing_time:
                print(f"[TIMEOUT] Stopping mosaic loading after {elapsed_time:.2f}s")
                break

            print(f"[PROGRESS] Processing mosaic {i+1}/{len(mertiles_to_load)}: tile {mertileid}")

            try:
                trace_start = time.time()
                trace = self.create_mosaic_image_trace(mertileid, opacity, colorscale)
                trace_time = time.time() - trace_start

                if trace:
                    traces.append(trace)
                    print(
                        f"[SUCCESS] Created mosaic trace for MER tile {mertileid} in {trace_time:.2f}s"
                    )
                else:
                    print(f"[WARNING] No trace created for MER tile {mertileid}")

            except Exception as e:
                print(f"[ERROR] Failed to create mosaic trace for tile {mertileid}: {e}")

        total_time = time.time() - start_time
        print(f"[TIMING] Total mosaic loading completed in {total_time:.2f}s")

        return traces

    def load_mask_overlay_traces_in_zoom(
        self,
        data: Dict[str, Any],
        relayout_data: Optional[Dict],
        opacity: float = 0.6,
        colorscale: str = "viridis",
    ) -> List[go.Scatter]:
        """
        Load mask overlay traces with strict performance limits and timing
        """
        start_time = time.time()
        mask_traces = []
        if not relayout_data:
            print("Debug: No relayout data available for mask overlay loading")
            return mask_traces

        # Extract zoom ranges from relayout data
        zoom_ranges = self._extract_zoom_ranges(relayout_data)
        if not zoom_ranges:
            print("Debug: Could not extract zoom ranges for mask overlay loading")
            return mask_traces

        ra_min, ra_max, dec_min, dec_max = zoom_ranges
        print(
            f"Debug: Loading mask overlays for zoom area: RA({ra_min:.3f}, {ra_max:.3f}), "
            f"Dec({dec_min:.3f}, {dec_max:.3f})"
        )

        # Find intersecting tiles
        mertiles_to_load = self._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)
        if not mertiles_to_load:
            print("Debug: No MER tiles with mosaics found in zoom area")
            return mask_traces

        # PERFORMANCE LIMITS: Strict limits for interactive experience
        max_masks = 5  # Maximum 5 mask overlays per zoom
        max_processing_time = 30  # Maximum 30 seconds total processing time
        if len(mertiles_to_load) > max_masks:
            print(f"Debug: Limiting to first {max_masks} mask overlays for performance")
            mertiles_to_load = mertiles_to_load[:max_masks]
        # Create traces for each mask overlay with timing checks
        for i, mertileid in enumerate(mertiles_to_load):
            # Check if we're running out of time
            elapsed_time = time.time() - start_time
            if elapsed_time > max_processing_time:
                print(f"[TIMEOUT] Stopping mask overlay loading after {elapsed_time:.2f}s")
                break

            print(
                f"[PROGRESS] Processing mask overlay {i+1}/{len(mertiles_to_load)}: tile {mertileid}"
            )

            try:
                trace_start = time.time()
                # Don't add colorbar for each tile, we'll add one at the end
                footprint_traces = self.create_mask_overlay_trace(
                    mertileid, opacity, colorscale, add_colorbar=False
                )
                trace_time = time.time() - trace_start

                if footprint_traces:
                    mask_traces.extend(footprint_traces)
                    print(
                        f"[SUCCESS] Created mask overlay traces for MER tile {mertileid} in {trace_time:.2f}s"
                    )
                else:
                    print(f"[WARNING] No mask overlay traces created for MER tile {mertileid}")

            except Exception as e:
                print(f"[ERROR] Failed to create mask overlay traces for tile {mertileid}: {e}")

        # Add a single colorbar for all mask overlays
        if mask_traces:
            weight_min, weight_max = 0.8, 1.0
            colorbar_trace = self._create_mask_colorbar_trace(
                weight_min, weight_max, colorscale, title="Coverage<br>Weight"
            )
            mask_traces.append(colorbar_trace)

        total_time = time.time() - start_time
        print(f"[TIMING] Total mask overlay loading completed in {total_time:.2f}s")
        return mask_traces

    def clear_traces_cache(self):
        """Clear the mosaic traces cache and free memory."""
        cache_size = len(self.traces_cache)
        self.traces_cache = {}  # Changed to dict for better performance
        self.current_mosaic_data = None

        # Force garbage collection to free memory
        import gc

        gc.collect()

        print(f"[CACHE] Cleared {cache_size} cached mosaic entries")

    def _create_placeholder_trace(
        self, mertileid: int, opacity: float = 0.5, colorscale: str = "gray"
    ) -> go.Heatmap:
        """Create a placeholder trace for large mosaic files that can't be loaded quickly."""
        # Create a small placeholder grid to indicate mosaic availability
        placeholder_size = 10
        placeholder_data = np.ones((placeholder_size, placeholder_size)) * 0.1  # Very dim

        # Create basic coordinate bounds (this could be improved with actual tile bounds)
        # For now, create a small area as a placeholder
        trace = go.Heatmap(
            z=placeholder_data,
            x=np.linspace(0, 1, placeholder_size),  # Placeholder coordinates
            y=np.linspace(0, 1, placeholder_size),  # Placeholder coordinates
            opacity=opacity * 0.3,  # Even more transparent for placeholder
            colorscale=colorscale,
            name=f"Mosaic {mertileid} (Placeholder)",
            hovertemplate=(
                f"<b>MER Tile {mertileid}</b><br>"
                "<i>Mosaic available but not loaded<br>"
                "(Large file - use async loading)</i><br>"
                "<extra></extra>"
            ),
            showscale=False,
        )

        return trace

    def get_healpix_boundaries(
        self, pixel_id, nside=16384, nest=True, step=4, mertileid=None, wcs_mosaic=None
    ):
        """
        Get the boundaries of a HEALPix pixel in RA/Dec and convert to image coordinates.

        Parameters:
        -----------
        pixel_id : int
            HEALPix pixel index
        nside : int
            HEALPix NSIDE parameter
        nest : bool
            Whether to use nested ordering
        step : int
            Number of boundary points per edge (4 edges total)

        Returns:
        --------
        x_pix, y_pix : arrays
            Pixel coordinates in the image
        """

        if wcs_mosaic is None:
            try:
                # Load mosaic data for this tile
                mosaic_info = self.get_mosaic_fits_data_by_mertile(mertileid)
                if not mosaic_info:
                    print(f"Warning: Could not load mosaic data for MER tile {mertileid}")
                    return None, None
                wcs_mosaic = mosaic_info["wcs"]
            except Exception as e:
                print(f"Warning: Exception while loading mosaic WCS for MER tile {mertileid}: {e}")
                return None, None

        ra, dec = hp.vec2ang(hp.boundaries(nside, pixel_id, step=step, nest=nest).T, lonlat=True)

        # Convert RA/Dec to pixel coordinates
        x_pix, y_pix = wcs_mosaic.wcs_world2pix(ra, dec, 0)

        return x_pix, y_pix


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
