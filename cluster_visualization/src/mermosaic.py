"""
Python class to handle the extraction and visualization of mosaic images.
"""

import glob
import json
import os
import queue
import re
import threading
import time
import warnings
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode
from urllib.request import urlopen

import healpy as hp
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objs as go
from astropy import wcs
from astropy.io import fits
from astropy.table import Table
from astropy.units import UnitsWarning
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

    FALLBACK_ESA_SOURCES = [
        {
            "id": "CDS/P/DSS2/color",
            "label": "DSS2 Color",
            "attribution": "DSS2 / CDS",
        },
        {
            "id": "CDS/P/Euclid/ERO/VIS",
            "label": "Euclid ERO VIS",
            "attribution": "Euclid ERO VIS / CDS",
        },
        {
            "id": "CDS/P/Euclid/Q1/VIS",
            "label": "Euclid Q1 VIS",
            "attribution": "Euclid Q1 VIS / CDS",
        },
        {
            "id": "CDS/P/Euclid/Q1/color",
            "label": "Euclid Q1 Color",
            "attribution": "Euclid Q1 Color / CDS",
        },
        {
            "id": "CDS/P/2MASS/color",
            "label": "2MASS Color",
            "attribution": "2MASS / CDS",
        },
        {
            "id": "CDS/P/allWISE/color",
            "label": "AllWISE Color",
            "attribution": "AllWISE / CDS",
        },
    ]

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

        # Corrected (combined) HEALPix mask — loaded lazily on first use
        self._corrected_mask_path: Optional[str] = (
            self.config.get_corrected_mask_fits()
            if self.config and hasattr(self.config, "get_corrected_mask_fits")
            else None
        )
        # Cached payload: (pixels, weights, ra, dec, nside) — populated by _load_corrected_mask()
        self._corrected_mask_data: Optional[tuple] = None

        self.mosaic_header = None
        self.mosaic_data: Optional[np.ndarray] = None
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

        # Mosaic provider and ESA discovery settings
        self.default_mosaic_provider = "local_fits"
        if hasattr(self.config, "get_mosaic_provider_default"):
            self.default_mosaic_provider = self.config.get_mosaic_provider_default()

        self.default_esa_source = "CDS/P/DSS2/color"
        if hasattr(self.config, "get_esa_source_default"):
            self.default_esa_source = self.config.get_esa_source_default()

        self.esa_source_discovery_url = ""
        if hasattr(self.config, "get_esa_mocserver_url"):
            self.esa_source_discovery_url = self.config.get_esa_mocserver_url()

        self.esa_cutout_base_url = ""
        if hasattr(self.config, "get_esa_cutout_base_url"):
            self.esa_cutout_base_url = self.config.get_esa_cutout_base_url()

        self.esa_timeout_seconds = 30
        if hasattr(self.config, "get_esa_timeout_seconds"):
            self.esa_timeout_seconds = self.config.get_esa_timeout_seconds()

        self.esa_source_cache_ttl_seconds = 21600
        if hasattr(self.config, "get_esa_source_cache_ttl_seconds"):
            self.esa_source_cache_ttl_seconds = self.config.get_esa_source_cache_ttl_seconds()

        self.esa_cutout_width = 768
        if hasattr(self.config, "get_esa_cutout_width"):
            self.esa_cutout_width = self.config.get_esa_cutout_width()

        self.esa_cutout_height = 768
        if hasattr(self.config, "get_esa_cutout_height"):
            self.esa_cutout_height = self.config.get_esa_cutout_height()

        # 'fits' = 32-bit float with WCS-derived bounds (default, best quality)
        # 'jpg'  = 8-bit JPEG with geometric cos(dec) bounds
        self.esa_cutout_format = "fits"
        if hasattr(self.config, "get_esa_cutout_format"):
            self.esa_cutout_format = self.config.get_esa_cutout_format()

        self.select_best_local_file = False
        if hasattr(self.config, "get_mosaic_select_best_local_file"):
            self.select_best_local_file = self.config.get_mosaic_select_best_local_file()

        self._cached_esa_sources: Optional[List[Dict[str, str]]] = None
        self._cached_esa_sources_ts: Optional[float] = None

    def _normalize_provider(self, provider: Optional[str]) -> str:
        """Normalize provider aliases used by UI and callback layers."""
        if not provider:
            provider = self.default_mosaic_provider

        provider_norm = str(provider).strip().lower()
        alias_map = {
            "local": "local_fits",
            "local_fits": "local_fits",
            "fits": "local_fits",
            "mer": "local_fits",
            "esa": "esa_sky",
            "esa_sky": "esa_sky",
            "esasky": "esa_sky",
        }
        return alias_map.get(provider_norm, "local_fits")

    def _build_cache_key(self, provider: str, source_id: Optional[str], mertileid: int) -> str:
        """Build a provider-aware cache key for mosaic data."""
        source_component = source_id or "default"
        fmt_component = self.esa_cutout_format if provider == "esa_sky" else "local"
        return f"{provider}|{source_component}|{mertileid}|{fmt_component}"

    def _extract_tile_bounds(
        self, data: Dict[str, Any], mertileid: int
    ) -> Optional[Tuple[float, float, float, float]]:
        """Get tile bounds (ra_min, ra_max, dec_min, dec_max) from catred polygons."""
        if "catred_info" not in data:
            return None

        tile_rows = data["catred_info"].loc[data["catred_info"]["mertileid"] == mertileid]
        if tile_rows.empty:
            return None

        tile_polygon = tile_rows.iloc[0].get("polygon")
        if tile_polygon is None:
            return None

        minx, miny, maxx, maxy = tile_polygon.bounds
        return (float(minx), float(maxx), float(miny), float(maxy))

    def get_available_mosaic_sources(self, provider: Optional[str] = None) -> List[Dict[str, str]]:
        """Return available sources for selected mosaic provider."""
        provider_norm = self._normalize_provider(provider)
        if provider_norm == "esa_sky":
            return self._discover_esa_sources()

        return [
            {
                "id": "local_mer",
                "label": "DpdMerBksMosaic",
                "attribution": "Local Euclid MER FITS",
            }
        ]

    def _discover_esa_sources(self) -> List[Dict[str, str]]:
        """Discover publicly available image surveys from a public MOC server endpoint."""
        now_ts = time.time()
        if (
            self._cached_esa_sources is not None
            and self._cached_esa_sources_ts is not None
            and (now_ts - self._cached_esa_sources_ts) < self.esa_source_cache_ttl_seconds
        ):
            return self._cached_esa_sources

        discovered_sources: List[Dict[str, str]] = []
        if self.esa_source_discovery_url:
            try:
                with urlopen(self.esa_source_discovery_url, timeout=self.esa_timeout_seconds) as resp:
                    payload = resp.read().decode("utf-8", errors="replace")
                records = json.loads(payload)

                if isinstance(records, list):
                    for record in records:
                        if not isinstance(record, dict):
                            continue

                        source_id = record.get("ID")
                        if not source_id:
                            continue

                        label = record.get("obs_title") or source_id
                        regime = record.get("obs_regime") or ""
                        attribution = record.get("obs_copyright") or "ESA/ESDC public HiPS"
                        if regime:
                            attribution = f"{attribution} ({regime})"

                        discovered_sources.append(
                            {
                                "id": str(source_id),
                                "label": str(label),
                                "attribution": str(attribution),
                            }
                        )
            except Exception as exc:
                print(f"[WARNING] ESA source discovery failed: {exc}")

        if not discovered_sources:
            discovered_sources = list(self.FALLBACK_ESA_SOURCES)

        # Dedupe while preserving order
        deduped: List[Dict[str, str]] = []
        seen = set()
        for src in discovered_sources:
            src_id = src.get("id")
            if src_id in seen:
                continue
            deduped.append(src)
            seen.add(src_id)

        self._cached_esa_sources = deduped
        self._cached_esa_sources_ts = now_ts
        return deduped

    def _load_mosaic_data_by_provider(
        self,
        mertileid: int,
        provider: Optional[str] = None,
        source_id: Optional[str] = None,
        tile_bounds: Optional[Tuple[float, float, float, float]] = None,
    ):
        """Load mosaic data for local FITS or ESA source provider."""
        provider_norm = self._normalize_provider(provider)
        normalized_source = source_id
        if provider_norm == "esa_sky" and not normalized_source:
            normalized_source = self.default_esa_source
        elif provider_norm == "local_fits":
            normalized_source = "local_mer"

        cache_key = self._build_cache_key(provider_norm, normalized_source, mertileid)
        if cache_key in self.traces_cache:
            print(f"[CACHE HIT] Using cached data for key {cache_key}")
            return self.traces_cache[cache_key]

        if provider_norm == "esa_sky":
            result = self._load_esa_cutout_by_mertile(
                mertileid=mertileid, source_id=normalized_source, tile_bounds=tile_bounds
            )
        else:
            result = self._load_local_mosaic_fits_data(mertileid=mertileid)

        if result is not None:
            result["provider"] = provider_norm
            result["source_id"] = normalized_source
            self.traces_cache[cache_key] = result

        return result

    def _load_local_mosaic_fits_data(self, mertileid: int):
        """Load local MER FITS tile from configured mosaic directory."""
        mosaic_dir = self.config.mosaic_dir
        if not mosaic_dir:
            print("[ERROR] paths.mosaic_dir is not configured")
            return None

        fits_files: List[str] = []
        try:
            fits_files = glob.glob(
                os.path.join(mosaic_dir, f"EUC_MER_BGSUB-MOSAIC-VIS_TILE{mertileid}*.fits.gz")
            )
        except Exception:
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

        if self.select_best_local_file:
            fits_file = self._select_best_local_mosaic_file(fits_files)
        else:
            fits_file = fits_files[0]
            print(
                "[SELECT] Using first MER mosaic candidate for speed "
                f"({os.path.basename(fits_file)})"
            )
        file_size_gb = os.path.getsize(fits_file) / (1024**3)

        # Check file size for initial performance optimization
        if file_size_gb > self.max_file_size_gb:
            print(f"[WARNING] Large file ({file_size_gb:.2f}GB) - may take longer to process")

        print(f"[LOADING] Processing mosaic for MER tile {mertileid} ({file_size_gb:.2f}GB)...")

        # Thread-safe FITS loading with timeout
        result_queue: queue.Queue = queue.Queue()
        error_queue: queue.Queue = queue.Queue()

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
                        {
                            "header": header,
                            "data": data,
                            "wcs": wcs_obj,
                            "file_path": fits_file,
                            "provider": "local_fits",
                            "source_id": "local_mer",
                            "attribution": "Local Euclid MER FITS",
                        }
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

        print(f"[SUCCESS] Processed MER tile {mertileid}")
        return result

    def _parse_mosaic_timestamp_score(self, file_path: str) -> int:
        """Extract sortable timestamp score from MER mosaic filename."""
        # Example segment: _20250818T005850.245906Z_
        basename = os.path.basename(file_path)
        match = re.search(r"_(\d{8})T(\d{6})\.(\d+)Z_", basename)
        if not match:
            return 0
        date_part, time_part, frac_part = match.groups()
        frac_part = (frac_part + "000000")[:6]
        return int(f"{date_part}{time_part}{frac_part}")

    def _estimate_file_valid_fraction(self, file_path: str) -> float:
        """Estimate usable-data fraction from a fast primary-HDU sample."""
        try:
            with fits.open(
                file_path,
                mode="readonly",
                ignore_missing_simple=True,
                memmap=False,
            ) as hdul:
                data = hdul[0].data
                if not isinstance(data, np.ndarray) or data.ndim != 2 or data.size == 0:
                    return -1.0

                step_y = max(1, data.shape[0] // 512)
                step_x = max(1, data.shape[1] // 512)
                sample = data[::step_y, ::step_x]

                valid_mask = np.isfinite(sample) & (np.abs(sample) < 1e30)
                return float(np.mean(valid_mask))
        except Exception as exc:
            print(f"[WARNING] Could not score mosaic candidate {os.path.basename(file_path)}: {exc}")
            return -1.0

    def _select_best_local_mosaic_file(self, fits_files: List[str]) -> str:
        """Select best local MER mosaic candidate deterministically."""
        scored_candidates = []
        for file_path in sorted(set(fits_files)):
            valid_fraction = self._estimate_file_valid_fraction(file_path)
            ts_score = self._parse_mosaic_timestamp_score(file_path)
            scored_candidates.append((valid_fraction, ts_score, file_path))

        # Prefer highest valid fraction, then latest timestamp, then lexicographic path.
        scored_candidates.sort(key=lambda x: (x[0], x[1], x[2]))
        best_valid, best_ts, best_file = scored_candidates[-1]
        print(
            "[SELECT] Chose MER mosaic candidate "
            f"{os.path.basename(best_file)} (valid_fraction={best_valid:.4f}, ts_score={best_ts})"
        )
        return best_file

    def _load_esa_cutout_by_mertile(
        self,
        mertileid: int,
        source_id: Optional[str],
        tile_bounds: Optional[Tuple[float, float, float, float]],
    ):
        """Load an ESA cutout image centered on selected MER tile bounds.

        The image format is selected by ``self.esa_cutout_format``:

        * ``'fits'`` (default) — requests a FITS file from hips2fits; bounds are
          derived exactly from the WCS header; data is 32-bit float with no
          compression artefacts.  Only the column axis is flipped so that
          ``data[0,0]`` = (min Dec, min RA) matches the Plotly heatmap convention.
        * ``'jpg'`` — requests a JPEG; bounds are computed geometrically using the
          cos(Dec) RA correction; both axes are flipped (PIL loads top-row first).

        In both cases the pixel values are normalized with the robust 1st–99.5th
        percentile stretch used for local FITS tiles.
        """
        if not tile_bounds:
            print(f"[WARNING] Missing tile bounds for ESA tile request: {mertileid}")
            return None

        if not self.esa_cutout_base_url:
            print("[ERROR] ESA cutout endpoint is not configured")
            return None

        ra_min, ra_max, dec_min, dec_max = tile_bounds
        center_ra = (ra_min + ra_max) / 2.0
        center_dec = (dec_min + dec_max) / 2.0
        fov_deg = max(abs(ra_max - ra_min), abs(dec_max - dec_min)) * 1.05
        if fov_deg <= 0:
            fov_deg = 0.02

        fmt = self.esa_cutout_format  # 'fits' or 'jpg'
        params = {
            "hips": source_id or self.default_esa_source,
            "ra": center_ra,
            "dec": center_dec,
            "fov": fov_deg,
            "width": self.esa_cutout_width,
            "height": self.esa_cutout_height,
            "projection": "TAN",
            "format": fmt,
        }
        cutout_url = f"{self.esa_cutout_base_url}?{urlencode(params)}"
        print(f"[ESA] Fetching {fmt.upper()} cutout for tile {mertileid}")

        try:
            with urlopen(cutout_url, timeout=self.esa_timeout_seconds) as resp:
                image_bytes = resp.read()

            if fmt == "fits":
                # ------------------------------------------------------------------
                # FITS path: 32-bit float, WCS-derived bounds, column-axis flip only
                # ------------------------------------------------------------------
                with fits.open(BytesIO(image_bytes), memmap=False) as hdul:
                    header = hdul[0].header.copy()
                    raw_data = hdul[0].data
                    if raw_data is None or raw_data.size == 0:
                        print(f"[WARNING] Empty FITS payload for ESA tile {mertileid}")
                        return None
                    # hips2fits may return 3-D or 4-D data when Stokes / spectral
                    # axes are present (NAXIS3, NAXIS4).  Drop all degenerate
                    # leading axes so we are left with a plain 2-D (height, width).
                    arr = raw_data
                    while arr.ndim > 2:
                        arr = arr[0]
                    image_array = arr.astype(np.float32, copy=True)
                    # .celestial extracts only the RA/Dec part of the WCS,
                    # avoiding "too many values to unpack" when the full header
                    # has extra axes.
                    wcs_obj = wcs.WCS(header).celestial

                img_h, img_w = image_array.shape

                # Derive bounds from the four corner pixels via WCS.
                # astropy pixel_to_world_values uses 0-indexed (x=col, y=row).
                corners_x = np.array([0.0, img_w - 1, img_w - 1, 0.0])
                corners_y = np.array([0.0, 0.0, img_h - 1, img_h - 1])
                ra_c, dec_c = wcs_obj.wcs_pix2world(corners_x, corners_y, 0)
                img_ra_min = float(np.min(ra_c))
                img_ra_max = float(np.max(ra_c))
                img_dec_min = float(np.min(dec_c))
                img_dec_max = float(np.max(dec_c))

                # Percentile normalization (same stretch as local FITS path).
                image_array = self._percentile_normalize(image_array)

                # Orientation fix: FITS data[i,j] = pixel(x=j, y=i).
                # For standard TAN (CD1_1 < 0, CD2_2 > 0):
                #   data[0,0] = (x=0, y=0) = max RA, min Dec
                # Plotly needs z[0,0] = (ra_min, dec_min) = min RA, min Dec.
                # Flip column axis only:
                image_array = np.ascontiguousarray(image_array[:, ::-1])

                return {
                    "header": header,
                    "data": image_array,
                    "wcs": wcs_obj,
                    "file_path": cutout_url,
                    "bounds": {
                        "ra_min": img_ra_min,
                        "ra_max": img_ra_max,
                        "dec_min": img_dec_min,
                        "dec_max": img_dec_max,
                        "ra_size_deg": img_ra_max - img_ra_min,
                        "dec_size_deg": img_dec_max - img_dec_min,
                    },
                    "cutout_format": "fits",
                    "provider": "esa_sky",
                    "source_id": source_id,
                    "attribution": "ESA/ESDC public HiPS via CDS hips2fits (FITS)",
                }

            else:
                # ------------------------------------------------------------------
                # JPEG path: 8-bit JPEG, geometric bounds, both-axes flip
                # ------------------------------------------------------------------
                pil_img = Image.open(BytesIO(image_bytes)).convert("L")
                image_array = np.asarray(pil_img, dtype=np.float32)

                if image_array.size == 0:
                    print(f"[WARNING] Empty JPEG payload for ESA tile {mertileid}")
                    return None

                # Simple geometric normalization: scale to [0, 1] by the
                # brightest pixel.  JPEG values are already 8-bit (0–255);
                # a more complex stretch would not recover lost precision.
                max_pixel = float(np.max(image_array))
                if max_pixel > 0:
                    image_array = image_array / max_pixel

                # Compute coordinate bounds.
                # hips2fits delivers fov_deg × fov_deg of sky angle;
                # 1 sky-angle degree = 1/cos(dec) degrees of RA coordinate.
                center_dec_rad = np.radians(center_dec)
                cos_dec = max(np.abs(np.cos(center_dec_rad)), 1e-6)
                half_fov_ra = fov_deg / (2.0 * cos_dec)
                half_fov_dec = fov_deg / 2.0
                img_ra_min = center_ra - half_fov_ra
                img_ra_max = center_ra + half_fov_ra
                img_dec_min = center_dec - half_fov_dec
                img_dec_max = center_dec + half_fov_dec

                # Orientation fix: PIL loads top-row first (max Dec, max RA at [0,0]).
                # Plotly needs z[0,0] = (ra_min, dec_min).  Flip both axes:
                image_array = np.ascontiguousarray(image_array[::-1, ::-1])

                return {
                    "header": None,
                    "data": image_array,
                    "wcs": None,
                    "file_path": cutout_url,
                    "bounds": {
                        "ra_min": img_ra_min,
                        "ra_max": img_ra_max,
                        "dec_min": img_dec_min,
                        "dec_max": img_dec_max,
                        "ra_size_deg": img_ra_max - img_ra_min,
                        "dec_size_deg": fov_deg,
                    },
                    "cutout_format": "jpg",
                    "provider": "esa_sky",
                    "source_id": source_id,
                    "attribution": "ESA/ESDC public HiPS via CDS hips2fits (JPEG)",
                }

        except Exception as exc:
            print(f"[ERROR] ESA cutout load failed for tile {mertileid}: {exc}")
            return None

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
                mosaicinfo = self.get_mosaic_fits_data_by_mertile(
                    mertileid, provider="local_fits", source_id="local_mer"
                )
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

    def get_mosaic_fits_data_by_mertile(
        self,
        mertileid,
        provider: Optional[str] = None,
        source_id: Optional[str] = None,
        tile_bounds: Optional[Tuple[float, float, float, float]] = None,
    ):
        """
        Load mosaic data for the selected provider with performance optimization.
        """
        return self._load_mosaic_data_by_provider(
            mertileid=mertileid,
            provider=provider,
            source_id=source_id,
            tile_bounds=tile_bounds,
        )

    def _extract_zoom_ranges(
        self, relayout_data: Dict
    ) -> Optional[Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]]:
        """Extract zoom ranges from Plotly relayout data."""
        ra_min: Optional[float] = None
        ra_max: Optional[float] = None
        dec_min: Optional[float] = None
        dec_max: Optional[float] = None

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

    def _read_effcovmask_table(self, hpmask_fits: str) -> Table:
        """Read HEALPix effective coverage table while silencing non-standard unit warnings."""
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=UnitsWarning,
                message=".*HEALPix pixel index.*",
            )
            return Table.read(hpmask_fits, format="fits", hdu=1)

    def _load_corrected_mask(self) -> Optional[tuple]:
        """Lazily load and cache the combined corrected HEALPix mask FITS file.

        Returns a tuple (pixels, weights, ra, dec, nside) where all arrays are
        numpy arrays for the full mask, or None if the mask is not configured /
        not found.
        """
        if self._corrected_mask_data is not None:
            return self._corrected_mask_data

        if not self._corrected_mask_path:
            print("[CORRECTED MASK] No corrected_mask_fits path configured")
            return None

        if not os.path.exists(self._corrected_mask_path):
            print(
                f"[CORRECTED MASK] File not found: {self._corrected_mask_path!r}. "
                "Falling back to per-tile effective coverage mask."
            )
            return None

        print(f"[CORRECTED MASK] Loading from {self._corrected_mask_path}")
        t0 = time.time()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UnitsWarning)
            with fits.open(self._corrected_mask_path, mode="readonly", memmap=True) as hf:
                hdr = hf[1].header
                nside = int(hdr.get("NSIDE", 16384))
                ordering = str(hdr.get("ORDERING", "NESTED")).upper()
                nested = ordering == "NESTED"
                pixels = np.asarray(hf[1].data["PIXEL"], dtype=np.int64)
                weights = np.asarray(hf[1].data["WEIGHT"], dtype=np.float32)

        ra, dec = hp.pix2ang(nside=nside, ipix=pixels, nest=nested, lonlat=True)
        self._corrected_mask_data = (pixels, weights, ra, dec, nside)
        print(
            f"[CORRECTED MASK] Loaded {len(pixels):,} pixels (nside={nside}) "
            f"in {time.time() - t0:.2f}s"
        )
        return self._corrected_mask_data

    def _get_mask_footprint_in_viewport(
        self,
        ra_min: float,
        ra_max: float,
        dec_min: float,
        dec_max: float,
        mask_type: str = "corrected",
        mertileid: Optional[int] = None,
    ) -> tuple:
        """Return (pixels, weights) arrays filtered to the given viewport.

        Args:
            ra_min, ra_max, dec_min, dec_max: Viewport bounds in degrees.
            mask_type: ``'corrected'`` uses the global corrected mask; ``'effcov'``
                uses the per-tile effective coverage mask (requires *mertileid*).
            mertileid: MER tile ID required when mask_type == 'effcov'.

        Returns:
            Tuple (pixels_arr, weights_arr) as numpy arrays.  Both are empty
            arrays when no matching pixels are found or an error occurs.
        """
        padding = 0.01  # small margin to include boundary pixels
        empty = (np.array([], dtype=np.int64), np.array([], dtype=np.float32))

        # Normalise bounds — Plotly sky plots reverse the RA axis so range[0] > range[1]
        ra_lo = min(ra_min, ra_max)
        ra_hi = max(ra_min, ra_max)
        dec_lo = min(dec_min, dec_max)
        dec_hi = max(dec_min, dec_max)

        if mask_type == "corrected":
            data = self._load_corrected_mask()
            if data is None:
                return empty
            pixels, weights, ra, dec, _ = data
            mask = (
                (weights > 0)
                & (ra >= ra_lo - padding)
                & (ra <= ra_hi + padding)
                & (dec >= dec_lo - padding)
                & (dec <= dec_hi + padding)
            )
            return pixels[mask], weights[mask]

        else:  # effcov — per-tile, requires mertileid
            if mertileid is None:
                print("[MASK] mertileid required for mask_type='effcov'")
                return empty
            try:
                matches = self.effcovmask_fileinfo_df.loc[
                    (self.effcovmask_fileinfo_df["mertileid"] == mertileid)
                    & (self.effcovmask_fileinfo_df["dataset_release"] == self.effcovmask_dsr)
                ]
                if matches.empty:
                    print(f"[MASK] No effcov mask file found for tile {mertileid}")
                    return empty
                hpmask_fits = matches.squeeze()["fits_file"]
                footprint = self._read_effcovmask_table(hpmask_fits)
                fp_ra, fp_dec = hp.pix2ang(
                    nside=16384, ipix=footprint["PIXEL"], nest=True, lonlat=True
                )
                mask = (
                    (footprint["WEIGHT"] > 0)
                    & (fp_ra >= ra_lo - padding)
                    & (fp_ra <= ra_hi + padding)
                    & (fp_dec >= dec_lo - padding)
                    & (fp_dec <= dec_hi + padding)
                )
                return np.asarray(footprint["PIXEL"][mask]), np.asarray(footprint["WEIGHT"][mask])
            except Exception as exc:
                print(f"[MASK] Error loading effcov mask for tile {mertileid}: {exc}")
                return empty

    def _find_intersecting_tiles(
        self,
        data: Dict[str, Any],
        ra_min: Optional[float],
        ra_max: Optional[float],
        dec_min: Optional[float],
        dec_max: Optional[float],
    ) -> List[int]:
        """Find MER tiles whose polygons intersect with the zoom box."""
        zoom_box = box(ra_min, dec_min, ra_max, dec_max)
        mertiles_to_load: List[int] = []

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

    def _percentile_normalize(self, image: np.ndarray) -> np.ndarray:
        """Normalize a 2D float array to [0, 1] using a robust 1st–99.5th
        percentile stretch with IQR outlier fencing.

        This is the same normalization used for local FITS tiles inside
        ``_process_mosaic_image`` and is applied to both FITS and JPEG
        ESA cutouts so that all providers share consistent contrast scaling.

        Returns a float32 array of the same shape.
        """
        valid_mask = np.isfinite(image) & (np.abs(image) < 1e30)
        if not np.any(valid_mask):
            return np.zeros_like(image, dtype=np.float32)

        finite_vals = image[valid_mask].astype(np.float64, copy=False)

        # Sample statistics for very large arrays.
        if finite_vals.size > self.max_pixels_for_stats:
            step = max(1, finite_vals.size // self.max_pixels_for_stats)
            stats_vals = finite_vals[::step]
        else:
            stats_vals = finite_vals

        # Robust IQR fencing to reject extreme outliers before stretch.
        q25 = float(np.nanpercentile(stats_vals, 25.0))
        q75 = float(np.nanpercentile(stats_vals, 75.0))
        iqr = q75 - q25
        if np.isfinite(iqr) and iqr > 0:
            core_vals = stats_vals[
                (stats_vals >= q25 - 10.0 * iqr) & (stats_vals <= q75 + 10.0 * iqr)
            ]
            if core_vals.size > 10_000:
                stats_vals = core_vals

        p_low = float(np.nanpercentile(stats_vals, 1.0))
        p_high = float(np.nanpercentile(stats_vals, 99.5))
        if not np.isfinite(p_low) or not np.isfinite(p_high) or p_high <= p_low:
            p_low = float(np.nanmin(stats_vals))
            p_high = float(np.nanmax(stats_vals))
        if not np.isfinite(p_low) or not np.isfinite(p_high) or p_high <= p_low:
            return np.zeros_like(image, dtype=np.float32)

        out = np.array(image, dtype=np.float64, copy=True)
        out[~valid_mask] = p_low
        out = np.clip(out, p_low, p_high)
        out = (out - p_low) / (p_high - p_low)
        return np.nan_to_num(out, nan=0.0, posinf=1.0, neginf=0.0).astype(np.float32)

    def _process_mosaic_image(
        self,
        mosaic_data: np.ndarray,
        target_width_and_height: Optional[Union[list, tuple]] = None,
        target_scale_factor: Optional[float] = None,
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

            print("Debug: Computing statistics...")

            mer_image = self._percentile_normalize(mosaic_data)

            if not np.any(mer_image):
                print("Warning: Invalid normalization bounds, returning zeros")
                return np.zeros((target_height, target_width), dtype=np.float32)

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
                .transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            )
            mer_array = np.nan_to_num(mer_array, nan=0.0, posinf=1.0, neginf=0.0)
            mer_array = np.clip(mer_array, 0.0, 1.0).astype(np.float32, copy=False)

            print(f"Debug: Final processed image shape: {mer_array.shape}")

            # Clean up large arrays to free memory
            del mer_image
            # if "sample_data" in locals():
            #     del sample_data

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
                    ra_coords = corners_world[:, 0].tolist()
                    dec_coords = corners_world[:, 1].tolist()
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
            if hasattr(mosaic_wcs, "_naxis") and mosaic_wcs._naxis is not None:
                orig_width = mosaic_wcs._naxis[0]
                orig_height = mosaic_wcs._naxis[1]
            elif hasattr(mosaic_wcs, "pixel_shape") and mosaic_wcs.pixel_shape is not None:
                orig_height, orig_width = mosaic_wcs.pixel_shape
            elif self.mosaic_data is not None:
                # Fallback: get from the stored mosaic data
                orig_height, orig_width = self.mosaic_data.shape
            else:
                raise ValueError("Original image dimensions not found in WCS or mosaic data")

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

    def _create_grouped_mask_traces(
        self,
        pixels: np.ndarray,
        weights: np.ndarray,
        opacity: float,
        colorscale: str,
        name_prefix: str = "Mask overlay",
        n_bins: int = 12,
        weight_min: float = 0.8,
        weight_max: float = 1.0,
    ) -> List[go.Scatter]:
        """Create a small number of grouped polygon traces to reduce Plotly lag."""
        grouped_x: List[List[Optional[float]]] = [[] for _ in range(n_bins)]
        grouped_y: List[List[Optional[float]]] = [[] for _ in range(n_bins)]
        grouped_count: List[int] = [0 for _ in range(n_bins)]

        for pix, weight in zip(pixels, weights):
            # Build polygon directly in world coordinates
            ra, dec = hp.vec2ang(hp.boundaries(16384, int(pix), step=2, nest=True).T, lonlat=True)
            ra = np.append(ra, ra[0]).tolist()
            dec = np.append(dec, dec[0]).tolist()

            weight_norm = (float(weight) - weight_min) / max(weight_max - weight_min, 1e-8)
            weight_norm = float(np.clip(weight_norm, 0.0, 1.0))
            bin_idx = min(n_bins - 1, int(weight_norm * n_bins))

            grouped_x[bin_idx].extend(ra + [None])
            grouped_y[bin_idx].extend(dec + [None])
            grouped_count[bin_idx] += 1

        traces: List[go.Scatter] = []
        try:
            colormap = getattr(plt.cm, colorscale)
        except AttributeError:
            print(f"Warning: Invalid colorscale '{colorscale}', defaulting to 'viridis'")
            colormap = plt.get_cmap("viridis")

        for bin_idx in range(n_bins):
            if grouped_count[bin_idx] == 0:
                continue

            color = colormap(bin_idx / max(n_bins - 1, 1))
            traces.append(
                go.Scatter(
                    x=grouped_x[bin_idx],
                    y=grouped_y[bin_idx],
                    mode="lines",
                    fill="toself",
                    fillcolor=(
                        f"rgba({int(color[0]*255)},{int(color[1]*255)},{int(color[2]*255)},{opacity})"
                    ),
                    line=dict(width=0.5, color="yellow"),
                    name=f"{name_prefix} bin {bin_idx}",
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

        return traces

    def create_mosaic_image_trace(
        self,
        mertileid: int,
        opacity: float = 0.5,
        colorscale: str = "gray",
        provider: Optional[str] = None,
        source_id: Optional[str] = None,
        tile_bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> Optional[go.Heatmap]:
        """Create a Plotly heatmap trace for a mosaic image."""
        provider_norm = self._normalize_provider(provider)
        # Load mosaic data for this tile
        mosaic_info = self.get_mosaic_fits_data_by_mertile(
            mertileid,
            provider=provider_norm,
            source_id=source_id,
            tile_bounds=tile_bounds,
        )
        if not mosaic_info:
            print(f"Warning: Could not load mosaic data for tile {mertileid}")
            return None

        if provider_norm == "esa_sky":
            # Data has already been normalized and orientation-corrected in
            # _load_esa_cutout_by_mertile (format-aware flip applied at load time).
            # FITS path:  column-flip only  → z[0,0] = (min Dec, min RA)
            # JPEG path:  both-axes flip    → z[0,0] = (min Dec, min RA)
            processed_image = np.asarray(mosaic_info["data"], dtype=np.float32)

            # Resize to match the display canvas so Plotly/browser does not
            # apply low-quality bilinear upscaling.  Orientation is already
            # correct, so we resize only — no additional flip.
            esa_h, esa_w = processed_image.shape
            target_w = self.img_width
            target_h = self.img_height
            if esa_w != target_w or esa_h != target_h:
                processed_image = np.array(
                    Image.fromarray(processed_image).resize(
                        (target_w, target_h), Image.Resampling.LANCZOS
                    ),
                    dtype=np.float32,
                )
                processed_image = np.clip(processed_image, 0.0, 1.0)
                print(
                    f"Debug: ESA cutout LANCZOS-resized {esa_w}×{esa_h} → {target_w}×{target_h}"
                )

            bounds = mosaic_info.get("bounds")
            if bounds is None:
                if tile_bounds is None:
                    print(f"Warning: Missing bounds for ESA tile {mertileid}")
                    return None
                bounds = {
                    "ra_min": tile_bounds[0],
                    "ra_max": tile_bounds[1],
                    "dec_min": tile_bounds[2],
                    "dec_max": tile_bounds[3],
                    "ra_size_deg": abs(tile_bounds[1] - tile_bounds[0]),
                    "dec_size_deg": abs(tile_bounds[3] - tile_bounds[2]),
                }
        else:
            # Process the local FITS image
            processed_image = self._process_mosaic_image(
                mosaic_info["data"], target_scale_factor=self.img_scale_factor
            )

            # Calculate coordinate bounds from FITS/WCS
            bounds = self._calculate_image_bounds_direct(mosaic_info["wcs"], processed_image)

        # Create coordinate arrays for the heatmap
        height, width = processed_image.shape
        x_coords = np.linspace(bounds["ra_min"], bounds["ra_max"], width)
        y_coords = np.linspace(bounds["dec_min"], bounds["dec_max"], height)

        # Add debug information about the tile size and coordinates
        print(f"Debug: Creating heatmap trace for tile {mertileid} ({provider_norm})")
        print(
            f"       - Tile size: {bounds.get('ra_size_deg', 'unknown'):.6f}° × {bounds.get('dec_size_deg', 'unknown'):.6f}°"
        )
        print(f"       - RA range: {bounds['ra_min']:.6f}° to {bounds['ra_max']:.6f}°")
        print(f"       - Dec range: {bounds['dec_min']:.6f}° to {bounds['dec_max']:.6f}°")
        print(f"       - Image shape: {height} × {width} pixels")

        source_label = source_id or mosaic_info.get("source_id") or "local_mer"
        provider_label = "ESA" if provider_norm == "esa_sky" else "MER"

        # Create the heatmap trace
        trace = go.Heatmap(
            z=processed_image,
            x=x_coords,
            y=y_coords,
            opacity=opacity,
            colorscale=colorscale,
            showscale=False,  # Don't show colorbar
            name=f"Mosaic ({provider_label}) {mertileid}",
            hovertemplate=(
                f"MER Tile: {mertileid}<br>"
                f"Provider: {provider_label}<br>"
                f"Source: {source_label}<br>"
                "RA: %{x:.6f}°<br>"
                "Dec: %{y:.6f}°<br>"
                "Intensity: %{z:.3f}<br>"
                f"Tile Size: {bounds.get('ra_size_deg', 'unknown'):.4f}° x {bounds.get('dec_size_deg', 'unknown'):.4f}°<br>"
                "<extra>Mosaic Image</extra>"
            ),
            customdata=np.full((height, width), source_label),
        )

        return trace

    def create_mask_overlay_trace(
        self,
        mertileid: int,
        opacity: float = 0.6,
        colorscale: str = "viridis",
        add_colorbar: bool = True,
        provider: Optional[str] = None,
        source_id: Optional[str] = None,
        tile_bounds: Optional[Tuple[float, float, float, float]] = None,
        mask_type: str = "corrected",
    ) -> Optional[List]:
        """Create Plotly scatter traces for a mask overlay.

        Args:
            mask_type: ``'corrected'`` (default) uses the global combined mask;
                ``'effcov'`` uses the per-tile effective coverage mask.
        """
        trace_start = time.time()

        # Determine the viewport bounds for pixel filtering.
        if tile_bounds is not None:
            ra_min_mosaic, ra_max_mosaic, dec_min_mosaic, dec_max_mosaic = tile_bounds
        else:
            # Fallback: derive bounds from local FITS/WCS.
            mosaic_info = self.get_mosaic_fits_data_by_mertile(
                mertileid,
                provider="local_fits",
                source_id="local_mer",
            )
            if not mosaic_info or mosaic_info.get("wcs") is None or mosaic_info.get("data") is None:
                print(f"Warning: Could not load local FITS/WCS for MER tile {mertileid}")
                return None

            mosaic_data = mosaic_info["data"]
            wcs_mosaic = mosaic_info["wcs"]

            ny, nx = mosaic_data.shape
            corners = wcs_mosaic.pixel_to_world([0, nx - 1, nx - 1, 0], [0, 0, ny - 1, ny - 1])
            ra_min_mosaic, ra_max_mosaic = corners.ra.deg.min(), corners.ra.deg.max()
            dec_min_mosaic, dec_max_mosaic = corners.dec.deg.min(), corners.dec.deg.max()

        print(f"RA range: {ra_min_mosaic:.4f} to {ra_max_mosaic:.4f}")
        print(f"Dec range: {dec_min_mosaic:.4f} to {dec_max_mosaic:.4f}")

        # Load footprint pixels filtered to this viewport.
        io_start = time.time()
        pix_arr, wt_arr = self._get_mask_footprint_in_viewport(
            ra_min_mosaic, ra_max_mosaic, dec_min_mosaic, dec_max_mosaic,
            mask_type=mask_type,
            mertileid=mertileid,
        )
        io_time = time.time() - io_start
        n_pix = len(pix_arr)
        print(f"Footprint pixels in viewport ({mask_type}): {n_pix}")
        if n_pix > 0:
            print(f"Weight range: {wt_arr.min():.3f} to {wt_arr.max():.3f}")

        # Create grouped traces for HEALPix footprint polygons.
        footprint_traces: List[go.Scatter] = []
        weight_min, weight_max = 0.8, 1.0

        if n_pix > 0:
            print(f"Creating grouped traces for {n_pix} HEALPix polygons...")
            polygon_start = time.time()
            footprint_traces = self._create_grouped_mask_traces(
                pixels=pix_arr,
                weights=wt_arr,
                opacity=opacity,
                colorscale=colorscale,
                name_prefix="Mask overlay",
                n_bins=12,
                weight_min=weight_min,
                weight_max=weight_max,
            )
            polygon_time = time.time() - polygon_start
        else:
            polygon_time = 0.0

        # Add a colorbar trace (invisible heatmap that only shows the colorbar).
        if footprint_traces and add_colorbar:
            colorbar_trace = self._create_mask_colorbar_trace(
                weight_min, weight_max, colorscale, title="Coverage<br>Weight"
            )
            footprint_traces.append(colorbar_trace)

        total_trace_time = time.time() - trace_start
        print(
            "[TIMING] Mask trace breakdown for tile "
            f"{mertileid} ({mask_type}): io={io_time:.2f}s, "
            f"polygon={polygon_time:.2f}s, total={total_trace_time:.2f}s"
        )

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

        mosaicinfo = self.get_mosaic_fits_data_by_mertile(
            mertileid, provider="local_fits", source_id="local_mer"
        )

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
        mask_type: str = "corrected",
    ) -> Optional[List[go.Scatter]]:
        """Create Plotly scatter traces for a mask overlay cutout.

        Args:
            mask_type: ``'corrected'`` (default) uses the global combined mask;
                ``'effcov'`` uses the per-tile effective coverage mask.
        """

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
            mask_traces = self.create_mask_overlay_trace(
                mertileid=mertileid, opacity=opacity, mask_type=mask_type
            )
            return mask_traces

        # Get the full mosaic WCS and shape
        print(f"Full mask overlay array shape: {data_cutout.shape}")

        # Get RA/Dec limits from the cutout WCS
        ny, nx = data_cutout.shape
        corners = wcs_cutout.pixel_to_world([0, nx - 1, nx - 1, 0], [0, 0, ny - 1, ny - 1])
        ra_min_mosaic, ra_max_mosaic = corners.ra.deg.min(), corners.ra.deg.max()
        dec_min_mosaic, dec_max_mosaic = corners.dec.deg.min(), corners.dec.deg.max()

        print(f"RA range: {ra_min_mosaic:.4f} to {ra_max_mosaic:.4f}")
        print(f"Dec range: {dec_min_mosaic:.4f} to {dec_max_mosaic:.4f}")

        # Load footprint pixels filtered to the cutout viewport.
        pix_arr, wt_arr = self._get_mask_footprint_in_viewport(
            ra_min_mosaic, ra_max_mosaic, dec_min_mosaic, dec_max_mosaic,
            mask_type=mask_type,
            mertileid=mertileid,
        )
        n_pix = len(pix_arr)
        print(f"Footprint pixels in cutout area ({mask_type}): {n_pix}")
        if n_pix > 0:
            print(f"Weight range: {wt_arr.min():.3f} to {wt_arr.max():.3f}")

        # Create grouped traces for HEALPix footprint polygons
        footprint_traces: List[go.Scatter] = []
        weight_min, weight_max = 0.8, 1.0

        if n_pix > 0:
            print(f"Creating grouped traces for {n_pix} HEALPix cutout polygons...")
            footprint_traces = self._create_grouped_mask_traces(
                pixels=pix_arr,
                weights=wt_arr,
                opacity=opacity,
                colorscale=colorscale,
                name_prefix="Mask overlay (cutout)",
                n_bins=12,
                weight_min=weight_min,
                weight_max=weight_max,
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
        provider: Optional[str] = None,
        source_id: Optional[str] = None,
        esa_cutout_format: Optional[str] = None,
        progress_callback=None,
    ) -> List[go.Heatmap]:
        """
        Load mosaic image traces with strict performance limits and timing
        """
        start_time = time.time()
        traces: List[go.Heatmap] = []
        provider_norm = self._normalize_provider(provider)

        # Override ESA cutout format for this call if provided by the UI.
        _original_format = self.esa_cutout_format
        if esa_cutout_format is not None:
            self.esa_cutout_format = esa_cutout_format

        if not relayout_data:
            self.esa_cutout_format = _original_format
            print("Debug: No relayout data available for mosaic loading")
            return traces

        # Extract zoom ranges from relayout data
        zoom_ranges = self._extract_zoom_ranges(relayout_data)
        if not zoom_ranges:
            self.esa_cutout_format = _original_format
            print("Debug: Could not extract zoom ranges for mosaic loading")
            return traces

        ra_min, ra_max, dec_min, dec_max = zoom_ranges
        print(
            f"Debug: Loading mosaics for zoom area: RA({ra_min:.3f}, {ra_max:.3f}), "
            f"Dec({dec_min:.3f}, {dec_max:.3f}), provider={provider_norm}, source={source_id}"
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
            if progress_callback is not None:
                progress_callback(i + 1, len(mertiles_to_load), mertileid)

            try:
                trace_start = time.time()
                tile_bounds = self._extract_tile_bounds(data, mertileid)
                trace = self.create_mosaic_image_trace(
                    mertileid,
                    opacity,
                    colorscale,
                    provider=provider_norm,
                    source_id=source_id,
                    tile_bounds=tile_bounds,
                )
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

        # Restore the format that was set before this call.
        self.esa_cutout_format = _original_format

        return traces

    def load_mask_overlay_traces_in_zoom(
        self,
        data: Dict[str, Any],
        relayout_data: Optional[Dict],
        opacity: float = 0.6,
        colorscale: str = "viridis",
        provider: Optional[str] = None,
        source_id: Optional[str] = None,
        mask_type: str = "corrected",
    ) -> List[go.Scatter]:
        """Load mask overlay traces for the current zoom viewport.

        Args:
            mask_type: ``'corrected'`` (default) loads the combined corrected
                mask in a single pass. ``'effcov'`` loops over intersecting
                MER tiles and loads per-tile effective coverage masks.
        """
        start_time = time.time()
        mask_traces: List[go.Scatter] = []
        provider_norm = self._normalize_provider(provider)
        if not relayout_data:
            print("Debug: No relayout data available for mask overlay loading")
            return mask_traces

        # Extract zoom ranges from relayout data
        zoom_ranges = self._extract_zoom_ranges(relayout_data)
        if not zoom_ranges:
            print("Debug: Could not extract zoom ranges for mask overlay loading")
            return mask_traces

        ra_min, ra_max, dec_min, dec_max = zoom_ranges
        if any(v is None for v in (ra_min, ra_max, dec_min, dec_max)):
            print("Debug: Incomplete zoom ranges for mask overlay loading")
            return mask_traces
        assert ra_min is not None and ra_max is not None
        assert dec_min is not None and dec_max is not None
        print(
            f"Debug: Loading mask overlays for zoom area: RA({ra_min:.3f}, {ra_max:.3f}), "
            f"Dec({dec_min:.3f}, {dec_max:.3f}), mask_type={mask_type}, "
            f"provider={provider_norm}, source={source_id}"
        )

        weight_min, weight_max = 0.8, 1.0

        if mask_type == "corrected":
            # ----------------------------------------------------------------
            # Corrected mask: single global pass — no per-tile loop needed.
            # ----------------------------------------------------------------
            pix_arr, wt_arr = self._get_mask_footprint_in_viewport(
                ra_min, ra_max, dec_min, dec_max, mask_type="corrected"
            )
            n_pix = len(pix_arr)
            print(f"[CORRECTED MASK] Viewport pixels: {n_pix}")

            if n_pix > 0:
                mask_traces = self._create_grouped_mask_traces(
                    pixels=pix_arr,
                    weights=wt_arr,
                    opacity=opacity,
                    colorscale=colorscale,
                    name_prefix="Mask overlay",
                    n_bins=12,
                    weight_min=weight_min,
                    weight_max=weight_max,
                )
            else:
                print("[CORRECTED MASK] No pixels found in viewport")

        else:
            # ----------------------------------------------------------------
            # Effective coverage mask: per-tile loop (original logic).
            # ----------------------------------------------------------------
            mertiles_to_load = self._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)
            if not mertiles_to_load:
                print("Debug: No MER tiles found in zoom area")
                return mask_traces

            max_masks = 5
            max_processing_time = 30
            tile_processing_time_total = 0.0
            if len(mertiles_to_load) > max_masks:
                print(f"Debug: Limiting to first {max_masks} mask overlays for performance")
                mertiles_to_load = mertiles_to_load[:max_masks]

            for i, mertileid in enumerate(mertiles_to_load):
                elapsed_time = time.time() - start_time
                if elapsed_time > max_processing_time:
                    print(f"[TIMEOUT] Stopping mask overlay loading after {elapsed_time:.2f}s")
                    break

                print(
                    f"[PROGRESS] Processing mask overlay {i+1}/{len(mertiles_to_load)}: "
                    f"tile {mertileid}"
                )

                try:
                    trace_start = time.time()
                    tile_bounds = self._extract_tile_bounds(data, mertileid)
                    footprint_traces = self.create_mask_overlay_trace(
                        mertileid,
                        opacity,
                        colorscale,
                        add_colorbar=False,
                        provider=provider_norm,
                        source_id=source_id,
                        tile_bounds=tile_bounds,
                        mask_type="effcov",
                    )
                    trace_time = time.time() - trace_start
                    tile_processing_time_total += trace_time

                    if footprint_traces:
                        mask_traces.extend(footprint_traces)
                        print(
                            f"[SUCCESS] Created mask overlay traces for MER tile {mertileid} "
                            f"in {trace_time:.2f}s"
                        )
                    else:
                        print(f"[WARNING] No mask overlay traces created for MER tile {mertileid}")

                except Exception as e:
                    print(
                        f"[ERROR] Failed to create mask overlay traces for tile {mertileid}: {e}"
                    )

        # Add a single colorbar for all mask overlays
        if mask_traces:
            colorbar_trace = self._create_mask_colorbar_trace(
                weight_min, weight_max, colorscale, title="Coverage<br>Weight"
            )
            mask_traces.append(colorbar_trace)

        total_time = time.time() - start_time
        print(
            f"[TIMING] Total mask overlay loading completed in {total_time:.2f}s "
            f"(mask_type={mask_type})"
        )
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
                mosaic_info = self.get_mosaic_fits_data_by_mertile(
                    mertileid, provider="local_fits", source_id="local_mer"
                )
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
