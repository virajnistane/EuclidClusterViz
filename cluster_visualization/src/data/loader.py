"""
Data loading and caching module for cluster visualization.

This module handles all data loading operations including:
- Merged cluster detection catalogs
- Individual tile data
- CATRED file information and polygons
- SNR range calculations
- Data validation and caching
"""

import datetime
import json
import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from astropy.io import fits

try:
    from cluster_visualization.utils.disk_cache import DiskCache, get_default_cache

    DISK_CACHE_AVAILABLE = True
except ImportError:
    print("Warning: Disk cache not available - using memory-only caching")
    DISK_CACHE_AVAILABLE = False

try:
    from cluster_visualization.utils.memory_manager import MemoryManager

    MEMORY_MANAGER_AVAILABLE = True
except ImportError:
    print("Warning: Memory manager not available - no memory limits enforced")
    MEMORY_MANAGER_AVAILABLE = False


class DataLoader:
    """Handles loading and caching of cluster detection data."""

    def __init__(self, config=None, use_disk_cache=True, max_memory_gb=None):
        """
        Initialize DataLoader with configuration.

        Args:
            config: Configuration object with path information
            use_disk_cache: Enable disk caching for faster subsequent loads (default: True)
            max_memory_gb: Maximum memory to use in GB (default: auto-detect 50% of RAM)
        """
        self.config = config
        self.data_cache = {}  # In-memory cache

        # Initialize memory manager
        if MEMORY_MANAGER_AVAILABLE:
            if max_memory_gb is None:
                max_memory_gb = MemoryManager.recommend_cache_size()
            self.memory_manager: Optional[MemoryManager] = MemoryManager(
                max_memory_gb=max_memory_gb
            )
        else:
            self.memory_manager = None

        # Initialize disk cache
        self.use_disk_cache = use_disk_cache and DISK_CACHE_AVAILABLE
        if self.use_disk_cache:
            self.disk_cache: Optional[DiskCache] = get_default_cache()
            print("Disk caching enabled - subsequent loads will be 5-10x faster")
        else:
            self.disk_cache = None

        # Import utilities from package structure
        try:
            from cluster_visualization.utils.myutils import get_xml_element

            self.get_xml_element = get_xml_element

        except ImportError as e:
            raise ImportError(f"Failed to import utilities: {e}")

    def load_data(self, select_algorithm: str = "PZWAV") -> Dict[str, Any]:
        """
        Load and prepare all data for visualization.

        Args:
            select_algorithm: Algorithm choice ('PZWAV', 'AMICO', or 'BOTH')

        Returns:
            Dict containing all loaded data:
            - data_detcluster_mergedcat: Merged cluster catalog
            - data_detcluster_by_cltile: Individual tile data by tile ID
            - catred_info: CATRED file information DataFrame
            - algorithm: Selected algorithm
            - snr_min/snr_max: SNR range for slider bounds

        Raises:
            FileNotFoundError: If required data files are missing
            ValueError: If algorithm is not supported
        """
        # Cleanup memory if needed before loading
        if self.memory_manager:
            current_mem = self.memory_manager.get_memory_stats()["rss_mb"]
            print(f"🔍 [Memory Check] Current: {current_mem:.1f} MB, Loading: {select_algorithm}")
            cleanup_performed = self.memory_manager.cleanup_if_needed(self.data_cache)
            if cleanup_performed:
                new_mem = self.memory_manager.get_memory_stats()["rss_mb"]
                print(f"   ↳ After cleanup: {new_mem:.1f} MB")

        # Check cache first
        if select_algorithm in self.data_cache:
            print(f"✓ [Cache HIT] Using cached data for {select_algorithm}")
            if self.memory_manager:
                self.memory_manager.mark_accessed(select_algorithm)
                print(f"   ↳ Marked {select_algorithm} as recently accessed (LRU)")
            data: Dict[str, Any] = self.data_cache[select_algorithm]
            return data

        print(f"⏳ [Cache MISS] Loading data for algorithm: {select_algorithm}")

        # Validate algorithm choice
        if select_algorithm not in ["PZWAV", "AMICO", "BOTH"]:
            print(f"Warning: Unknown algorithm '{select_algorithm}'. Using 'PZWAV' as default.")
            select_algorithm = "PZWAV"

        # Get paths based on configuration
        paths = self._get_paths(select_algorithm)

        # Validate critical paths
        self._validate_paths(paths)

        # Load data components and calculate SNR ranges - check for gluematchcat first, fallback to separate files
        (
            data_detcluster_mergedcat,
            snr_min_pzwav,
            snr_max_pzwav,
            snr_min_amico,
            snr_max_amico,
        ) = self._load_data_detcluster_mergedcat_with_minmax_snr(paths, select_algorithm)
        data_detcluster_by_cltile = self._load_data_detcluster_by_cltile(paths, select_algorithm)

        catred_fileinfo_df = self._load_catred_info(paths)
        catred_dsr = self.config.get_catred_dsr() if self.config else None
        effcovmask_fileinfo_df = self._load_effcovmask_info(paths)
        effcovmask_dsr = self.config.get_effcovmask_dsr() if self.config else None

        # # Calculate SNR range for UI slider
        # snr_min = float(data_detcluster_mergedcat['SNR_CLUSTER'].min())
        # snr_max = float(data_detcluster_mergedcat['SNR_CLUSTER'].max())
        # print(f"SNR range: {snr_min:.3f} to {snr_max:.3f}")

        # Calculate redshift range for UI slider
        z_min = float(data_detcluster_mergedcat["Z_CLUSTER"].min())
        z_max = float(data_detcluster_mergedcat["Z_CLUSTER"].max())
        print(f"Redshift range: {z_min:.3f} to {z_max:.3f}")

        # Assemble final data structure
        data = {
            "data_detcluster_mergedcat": data_detcluster_mergedcat,
            "data_detcluster_by_cltile": data_detcluster_by_cltile,
            "catred_info": catred_fileinfo_df,
            "catred_dsr": catred_dsr,
            "effcovmask_info": effcovmask_fileinfo_df,
            "effcovmask_dsr": effcovmask_dsr,
            "algorithm": select_algorithm,
            "snr_threshold_lower": None,  # Will be set by UI
            "snr_threshold_upper": None,  # Will be set by UI
            "snr_min_pzwav": snr_min_pzwav,
            "snr_max_pzwav": snr_max_pzwav,
            "snr_min_amico": snr_min_amico,
            "snr_max_amico": snr_max_amico,
            "z_min": z_min,
            "z_max": z_max,
        }

        # Check if we have room to cache in memory
        if self.memory_manager:
            mem_before = self.memory_manager.check_memory()
            current_mem_mb = mem_before / 1024**2
            max_mem_mb = self.memory_manager.max_memory_bytes / 1024**2

            print(f"💾 [Cache Decision] Current: {current_mem_mb:.1f} MB / {max_mem_mb:.1f} MB")

            # Try caching and check if we're still under threshold
            self.data_cache[select_algorithm] = data
            mem_after = self.memory_manager.check_memory()

            if mem_after < self.memory_manager.warning_threshold_bytes:
                # Successfully cached and still under limit
                self.memory_manager.mark_accessed(select_algorithm)
                new_mem_mb = mem_after / 1024**2
                data_size_mb = (mem_after - mem_before) / 1024**2
                print(f"   ↳ ✓ Cached in memory: {select_algorithm} (+{data_size_mb:.1f} MB)")
                print(
                    f"   ↳ Memory now: {new_mem_mb:.1f} MB (usage: {(new_mem_mb/max_mem_mb)*100:.1f}%)"
                )
            else:
                # Would exceed limit - remove from cache
                del self.data_cache[select_algorithm]
                print(f"   ↳ ⚠️  Skipping memory cache for {select_algorithm} (would exceed limit)")
                print(f"   ↳ Data will be loaded from disk cache on next request.")
        else:
            # No memory manager - cache everything
            self.data_cache[select_algorithm] = data
            print(f"💾 Cached in memory: {select_algorithm} (no memory limit)")

        return data

    def _get_paths(self, algorithm: str) -> Dict[str, str]:
        """Get file paths based on configuration or fallback."""
        assert self.config, "Configuration is not set"

        # Check if gluematchcat exists
        gluematchcat_xml = self.config.get_gluematchcat_clusters_xml()
        use_gluematchcat = gluematchcat_xml is not None and os.path.exists(gluematchcat_xml)

        # Always get detintile files for per-tile data
        detfiles_list_files_dict = self.config.get_detintile_list_files(algorithm)

        if use_gluematchcat:
            print(f"✓ Using GlueMatchCat for merged data (includes both PZWAV and AMICO)")
            print(f"✓ Using separate DetInTile files for per-tile data")
            paths = {
                "use_gluematchcat": True,
                "gluematchcat_dir": self.config.gluematchcat_dir,
                "gluematchcat_xml": gluematchcat_xml,
                "mergedetcat_dir": self.config.mergedetcat_dir,
                "detintile_dir": self.config.detintile_dir,
                "detfiles_list_files_dict": detfiles_list_files_dict,
                "catred_fileinfo_csv": self.config.get_catred_fileinfo_csv(),
                "catred_polygon_pkl": self.config.get_catred_polygons_pkl(),
                "effcovmask_fileinfo_csv": self.config.get_effcovmask_fileinfo_csv(),
            }
        else:
            print(f"✓ Using separate MergeDetCat files for {algorithm}")
            mergedetcat_xml_files_dict: Dict[str, str] = self.config.get_mergedetcat_xml_files(
                algorithm
            )

            paths = {
                "use_gluematchcat": False,
                "mergedetcat_dir": self.config.mergedetcat_dir,
                "mergedetcat_xml_files_dict": mergedetcat_xml_files_dict,
                "detintile_dir": self.config.detintile_dir,
                "detfiles_list_files_dict": detfiles_list_files_dict,
                "catred_fileinfo_csv": self.config.get_catred_fileinfo_csv(),
                "catred_polygon_pkl": self.config.get_catred_polygons_pkl(),
                "effcovmask_fileinfo_csv": self.config.get_effcovmask_fileinfo_csv(),
            }

        return paths

    def _validate_paths(self, paths: Dict[str, str]) -> None:
        """Validate that critical paths exist."""
        if paths.get("use_gluematchcat"):
            critical_paths = ["gluematchcat_xml", "gluematchcat_dir", "detintile_dir"]
        else:
            critical_paths = ["mergedetcat_xml_files_dict", "mergedetcat_dir", "detintile_dir"]

        for path_key in critical_paths:
            if path_key == "mergedetcat_xml_files_dict":
                path_value = paths[path_key]
                if not isinstance(path_value, dict):
                    raise ValueError(
                        f"Expected dict for 'mergedetcat_xml_files_dict', got {type(path_value)}"
                    )
                for xml_path in path_value.values():
                    if not os.path.exists(xml_path):
                        raise FileNotFoundError(f"MergeDetCat XML not found: {xml_path}")
            else:
                path = paths[path_key]
                if not os.path.exists(path):
                    raise FileNotFoundError(
                        f"{path_key.replace('_', ' ').title()} not found: {path}"
                    )

    def _load_data_detcluster_mergedcat_with_minmax_snr(
        self, paths: Dict[str, str], algorithm: str
    ) -> Tuple[np.ndarray, Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Load merged detection catalog from XML and FITS files."""
        # Try disk cache first
        if self.use_disk_cache and self.disk_cache is not None:
            cache_key = f"merged_catalog_{algorithm}"
            source_files = self._get_merged_catalog_source_files(paths)

            cached: Optional[
                Tuple[
                    np.ndarray, Optional[float], Optional[float], Optional[float], Optional[float]
                ]
            ] = self.disk_cache.get(cache_key, source_files)
            if cached is not None:
                return cached  # Tuple of (data, snr_min_pzwav, snr_max_pzwav, snr_min_amico, snr_max_amico)

        # Cache miss - load data
        if paths.get("use_gluematchcat"):
            # Load from gluematchcat
            gluematchcat_xml = paths["gluematchcat_xml"]
            if not os.path.exists(gluematchcat_xml):
                raise FileNotFoundError(f"GlueMatchCat XML not found: {gluematchcat_xml}")

            # Extract FITS filename from XML
            fits_filename = self.get_xml_element(
                gluematchcat_xml, "Data/FullDetectionsFile/DataContainer/FileName"
            ).text
            fitsfile = os.path.join(paths["gluematchcat_dir"], "data", fits_filename)

            # Check if file exists, if not try without checking (will raise error with better message)
            if not os.path.exists(fitsfile):
                print(f"Warning: FITS file not found at {fitsfile}")
                print(f"This may indicate a path configuration issue")

            print(f"Loading clusters from GlueMatchCat: {os.path.basename(fitsfile)}")
            with fits.open(fitsfile, mode="readonly", memmap=True) as hdul:
                # Convert to numpy array immediately to avoid memmap issues
                data_all = np.array(hdul[1].data)

            # Filter by algorithm if not BOTH
            if algorithm == "BOTH":
                data_merged = data_all
                snr_min_pzwav = float(
                    data_merged[data_merged["DET_CODE_NB"] == 2]["SNR_CLUSTER"].min()
                )
                snr_max_pzwav = float(
                    data_merged[data_merged["DET_CODE_NB"] == 2]["SNR_CLUSTER"].max()
                )
                snr_min_amico = float(
                    data_merged[data_merged["DET_CODE_NB"] == 1]["SNR_CLUSTER"].min()
                )
                snr_max_amico = float(
                    data_merged[data_merged["DET_CODE_NB"] == 1]["SNR_CLUSTER"].max()
                )
                print(f"Loaded {len(data_merged)} total clusters (PZWAV + AMICO)")
            else:
                # Filter by DET_CODE_NB or ID_DET_AMICO columns
                if algorithm == "PZWAV":
                    # Keep rows where DET_CODE_NB is 2
                    data_merged = data_all[data_all["DET_CODE_NB"] == 2]
                    print(f"Loaded {len(data_merged)} PZWAV clusters from GlueMatchCat")
                    snr_min_pzwav = float(data_merged["SNR_CLUSTER"].min())
                    snr_max_pzwav = float(data_merged["SNR_CLUSTER"].max())
                    snr_min_amico = None
                    snr_max_amico = None
                elif algorithm == "AMICO":
                    # Keep rows where DET_CODE_NB is 1
                    data_merged = data_all[data_all["DET_CODE_NB"] == 1]
                    print(f"Loaded {len(data_merged)} AMICO clusters from GlueMatchCat")
                    snr_min_pzwav = None
                    snr_max_pzwav = None
                    snr_min_amico = float(data_merged["SNR_CLUSTER"].min())
                    snr_max_amico = float(data_merged["SNR_CLUSTER"].max())
        else:
            # Load from separate mergedetcat files
            mergedetcat_xml_files_dict = paths["mergedetcat_xml_files_dict"]

            if algorithm == "BOTH":
                # Load both files and combine
                all_data = []
                assert isinstance(mergedetcat_xml_files_dict, dict)
                for det_xml_key, det_xml in mergedetcat_xml_files_dict.items():
                    if not os.path.exists(det_xml):
                        raise FileNotFoundError(f"Merged detection XML not found: {det_xml}")

                    fits_filename = self.get_xml_element(
                        det_xml, "Data/ClustersFile/DataContainer/FileName"
                    ).text
                    fitsfile = os.path.join(paths["mergedetcat_dir"], "data", fits_filename)

                    print(f"Loading merged catalog from: {os.path.basename(fitsfile)}")
                    with fits.open(fitsfile, mode="readonly", memmap=True) as hdul:
                        all_data.append(hdul[1].data)

                    if det_xml_key == "mergedetcat_pzwav":
                        print(f"Loaded {len(all_data[-1])} PZWAV merged clusters")
                        snr_min_pzwav = float(all_data[-1]["SNR_CLUSTER"].min())
                        snr_max_pzwav = float(all_data[-1]["SNR_CLUSTER"].max())
                    elif det_xml_key == "mergedetcat_amico":
                        print(f"Loaded {len(all_data[-1])} AMICO merged clusters")
                        snr_min_amico = float(all_data[-1]["SNR_CLUSTER"].min())
                        snr_max_amico = float(all_data[-1]["SNR_CLUSTER"].max())
                    else:
                        snr_min_pzwav = None
                        snr_max_pzwav = None
                        snr_min_amico = None
                        snr_max_amico = None

                # Combine arrays
                data_merged = np.concatenate(all_data)
                print(f"Loaded {len(data_merged)} total merged clusters (combined)")
            else:
                # Load single file
                assert isinstance(mergedetcat_xml_files_dict, dict)
                det_xml = mergedetcat_xml_files_dict[f"mergedetcat_{algorithm.lower()}"]
                if not os.path.exists(det_xml):
                    raise FileNotFoundError(f"Merged detection XML not found: {det_xml}")

                fits_filename = self.get_xml_element(
                    det_xml, "Data/ClustersFile/DataContainer/FileName"
                ).text
                fitsfile = os.path.join(paths["mergedetcat_dir"], "data", fits_filename)

                print(f"Loading merged catalog from: {os.path.basename(fitsfile)}")
                with fits.open(fitsfile, mode="readonly", memmap=True) as hdul:
                    data_merged = hdul[1].data

                print(f"Loaded {len(data_merged)} {algorithm} merged clusters")

                if algorithm == "PZWAV":
                    snr_min_pzwav = float(data_merged["SNR_CLUSTER"].min())
                    snr_max_pzwav = float(data_merged["SNR_CLUSTER"].max())
                    snr_min_amico = None
                    snr_max_amico = None
                elif algorithm == "AMICO":
                    snr_min_pzwav = None
                    snr_max_pzwav = None
                    snr_min_amico = float(data_merged["SNR_CLUSTER"].min())
                    snr_max_amico = float(data_merged["SNR_CLUSTER"].max())

        result = (data_merged, snr_min_pzwav, snr_max_pzwav, snr_min_amico, snr_max_amico)

        # Save to disk cache
        if self.use_disk_cache and self.disk_cache is not None:
            cache_key = f"merged_catalog_{algorithm}"
            source_files = self._get_merged_catalog_source_files(paths)
            self.disk_cache.set(cache_key, result, source_files)

        return result

    def _load_data_detcluster_by_cltile(
        self, paths: Dict[str, str], algorithm: str
    ) -> Dict[str, Dict[str, Any]]:
        """Load individual tile detection data from separate detintile files."""
        # Try disk cache first
        if self.use_disk_cache and self.disk_cache is not None:
            cache_key = f"tile_data_{algorithm}"
            source_files = self._get_tile_data_source_files(paths)

            cached: Optional[Dict[str, Dict[str, Any]]] = self.disk_cache.get(
                cache_key, source_files
            )
            if cached is not None:
                return cached

        # Cache miss - load data
        # Always load from separate detintile files (even when using gluematchcat for merged data)
        detfiles_list_files_dict = paths["detfiles_list_files_dict"]

        data_by_tile = {}
        assert isinstance(detfiles_list_files_dict, dict)
        for detfiles_list_path_key, detfiles_list_path in detfiles_list_files_dict.items():
            if not os.path.exists(detfiles_list_path):
                print(f"Warning: Detection files list not found: {detfiles_list_path}")
                continue

            # Determine algorithm from the list file path
            tile_algorithm = None
            if detfiles_list_path_key == "detintile_pzwav_list":
                tile_algorithm = "PZWAV"
            elif detfiles_list_path_key == "detintile_amico_list":
                tile_algorithm = "AMICO"

            with open(detfiles_list_path, "r") as f:
                detfiles_list = json.load(f)

            for file in detfiles_list:
                # Extract tile information from XML files

                try:
                    assert os.path.isabs(file)
                    print(f"Found absolute path for tile XML: {file}")
                    xml_path = file
                    dirpath = os.path.dirname(xml_path)
                    while os.path.exists(os.path.join(dirpath, "data/")):
                        dirpath = os.path.dirname(dirpath)

                    print(f"Determined directory path for data: {dirpath}")

                except AssertionError:
                    dirs_to_checks = [
                        paths["mergedetcat_dir"],
                        paths["detintile_dir"],
                        os.path.join(paths["mergedetcat_dir"], "inputs"),
                        os.path.join(paths["detintile_dir"], "inputs"),
                    ]

                    try:
                        xml_path = None
                        dirpath = None
                        for dir_check in dirs_to_checks:
                            potential_path = os.path.join(dir_check, file)
                            if os.path.exists(potential_path):
                                xml_path = potential_path
                                dirpath = (
                                    dir_check
                                    if os.path.basename(dir_check) != "inputs"
                                    else os.path.dirname(dir_check)
                                )
                                break
                        assert (
                            xml_path is not None
                        ), f"File not found in expected directories: {file}"
                    except AssertionError:
                        print(f"Warning: XML file not found in expected directories: {file}")
                        continue

                tile_file = self.get_xml_element(
                    xml_path, "Data/SpatialInformation/DataContainer/FileName"
                ).text
                # Use {dirpath}/data for tile data (even when using gluematchcat for merged data)
                tile_file_path = os.path.join(dirpath, "data", tile_file)

                if not os.path.exists(tile_file_path):
                    print(f"Warning: Tile definition file not found: {tile_file_path}")
                    continue

                with open(tile_file_path, "r") as tf:
                    tile_info = json.load(tf)
                tile_id = tile_info["TILE_ID"]

                # When loading BOTH algorithms, use composite key to avoid overwriting
                # Format: "tileid" for single algorithm, "tileid_ALGORITHM" for BOTH
                if algorithm == "BOTH" and tile_algorithm:
                    tile_key = f"{tile_id}_{tile_algorithm}"
                else:
                    tile_key = tile_id

                fits_file = self.get_xml_element(
                    xml_path, "Data/ClustersFile/DataContainer/FileName"
                ).text
                # Load FITS data for this tile
                fits_path = os.path.join(dirpath, "data", fits_file)
                if not os.path.exists(fits_path):
                    print(f"Warning: FITS file not found: {fits_path}")
                    continue

                # Try to find density files
                dens_xml = None
                dens_fits = None
                for i in os.listdir(os.path.dirname(xml_path)):
                    try:
                        assert i.endswith(".xml")
                        dens_fits = self.get_xml_element(
                            os.path.join(os.path.dirname(xml_path), i),
                            "Data/PZWavDensFile/DataContainer/FileName",
                        ).text
                        assert "DENSITIES" in dens_fits
                        assert (
                            self.get_xml_element(
                                os.path.join(os.path.dirname(xml_path), i),
                                "Data/SpatialInformation/DataContainer/FileName",
                            ).text
                            == tile_file
                        )
                        dens_xml = os.path.join(os.path.dirname(xml_path), i)
                        break
                    except:
                        continue

                with fits.open(fits_path, mode="readonly", memmap=True) as hdul:
                    tile_data = hdul[1].data

                data_by_tile[tile_key] = {
                    "detxml_file": xml_path,
                    "detfits_file": fits_path,
                    "cltiledef_file": tile_file_path,
                    "densxml_file": dens_xml if dens_xml else None,
                    "densfits_file": (
                        os.path.join(dirpath, "data", dens_fits) if dens_fits else None
                    ),
                    "detfits_data": tile_data,
                    "algorithm": tile_algorithm,  # Add algorithm identifier
                    "tile_id": tile_id,  # Store original tile_id separately
                }

        data_by_tile = dict(sorted(data_by_tile.items()))
        print(f"Loaded {len(data_by_tile)} individual tiles")

        # Save to disk cache
        if self.use_disk_cache and self.disk_cache is not None:
            cache_key = f"tile_data_{algorithm}"
            source_files = self._get_tile_data_source_files(paths)
            self.disk_cache.set(cache_key, data_by_tile, source_files)

        return data_by_tile

    def _load_catred_info(self, paths: Dict[str, str]) -> pd.DataFrame:
        """Load CATRED file information and polygon data."""
        # Try disk cache first
        if self.use_disk_cache and self.disk_cache is not None:
            cache_key = "catred_fileinfo"
            catred_dir = self._get_catred_dir(paths)
            source_files = [catred_dir] if os.path.exists(catred_dir) else []

            cached = self.disk_cache.get(cache_key, source_files)
            if cached is not None:
                return cached

        # Cache miss - load or generate data
        catred_fileinfo_csv = paths["catred_fileinfo_csv"]
        catred_polygon_pkl = paths["catred_polygon_pkl"]
        regenerate = False

        # Get catred directory from config
        if self.config and hasattr(self.config, "catred_dir"):
            catred_dir = self.config.catred_dir
        else:
            # Fallback to rr2_downloads/DpdLE3clFullInputCat
            catred_dir = os.path.join(
                os.path.dirname(paths["catred_fileinfo_csv"]), "DpdLE3clFullInputCat"
            )

        if not os.path.exists(catred_dir):
            print(f"Warning: CATRED directory not found at {catred_dir}")
            return pd.DataFrame()

        # Load CSV file info or generate it if it doesn't exist
        catred_fileinfo_df = pd.DataFrame()
        if os.path.exists(catred_fileinfo_csv):
            print(f"catred_fileinfo.csv already exists in {os.path.dirname(catred_fileinfo_csv)}")
            catred_fileinfo_df = pd.read_csv(catred_fileinfo_csv)
            catred_fileinfo_df.set_index("uid", inplace=True)
            try:
                catred_fileinfo_df_wd = pd.read_csv(
                    catred_fileinfo_csv.replace(".csv", "_with_duplicates.csv")
                )
                # Get list of XML files
                catredxmlfiles = [i for i in os.listdir(catred_dir) if i.endswith(".xml")]
                for subdir in os.listdir(catred_dir):
                    subdir_path = os.path.join(catred_dir, subdir)
                    if os.path.isdir(subdir_path):
                        subdir_xmlfiles = [i for i in os.listdir(subdir_path) if i.endswith(".xml")]
                        catredxmlfiles.extend([os.path.join(subdir, i) for i in subdir_xmlfiles])
                # Check for mismatch in number of entries
                if len(catred_fileinfo_df_wd) != len(catredxmlfiles):
                    print(
                        "Warning: Number of entries in catred_fileinfo.csv does not match number of CATRED XML files. Regenerating."
                    )
                    regenerate = True
                    catred_fileinfo_df = self._generate_catred_fileinfo(
                        paths, catredxmlfiles=catredxmlfiles
                    )
            except FileNotFoundError:
                pass
            print("Loaded catred file info")
        else:
            print(f"catred_fileinfo.csv does not exist in {os.path.dirname(catred_fileinfo_csv)}")
            catred_fileinfo_df = self._generate_catred_fileinfo(paths)

        # Load polygon data or generate it if it doesn't exist
        if os.path.exists(catred_polygon_pkl) and not catred_fileinfo_df.empty:
            with open(catred_polygon_pkl, "rb") as f:
                catred_polygon_info = pickle.load(f)
            catred_fileinfo_df["polygon"] = pd.Series(catred_polygon_info)
            print("Loaded catred polygons")
        elif not catred_fileinfo_df.empty or regenerate:
            print(
                f"catred polygons not found at {catred_polygon_pkl} or regeneration requested. Generating polygons."
            )
            catred_fileinfo_df = self._generate_catred_polygons(catred_fileinfo_df, paths)
        else:
            print("Warning: Cannot generate polygons - catred_fileinfo_df is empty")

        # Save to disk cache
        if self.use_disk_cache and not catred_fileinfo_df.empty and self.disk_cache is not None:
            cache_key = "catred_fileinfo"
            catred_dir = self._get_catred_dir(paths)
            source_files = [catred_dir] if os.path.exists(catred_dir) else []
            self.disk_cache.set(cache_key, catred_fileinfo_df, source_files)

        return catred_fileinfo_df

    def _generate_catred_fileinfo(
        self, paths: Dict[str, str], catredxmlfiles: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Generate catred_fileinfo.csv from XML files."""
        print("Processing catred XML files to create catred_fileinfo dictionary")

        # Get catred directory from config
        if self.config and hasattr(self.config, "catred_dir"):
            catred_dir = self.config.catred_dir
        else:
            # Fallback to rr2_downloads/DpdLE3clFullInputCat
            catred_dir = os.path.join(
                os.path.dirname(paths["catred_fileinfo_csv"]), "DpdLE3clFullInputCat"
            )

        catred_fileinfo_csv = paths["catred_fileinfo_csv"]

        if not os.path.exists(catred_dir):
            print(f"Warning: CATRED directory not found at {catred_dir}")
            return pd.DataFrame()

        if catredxmlfiles is None:
            # Get list of XML files
            catredxmlfiles = [i for i in os.listdir(catred_dir) if i.endswith(".xml")]

            # Get xml files from each subdirectory (named for DSR) too
            for subdir in os.listdir(catred_dir):
                subdir_path = os.path.join(catred_dir, subdir)
                if os.path.isdir(subdir_path):
                    subdir_xmlfiles = [i for i in os.listdir(subdir_path) if i.endswith(".xml")]
                    catredxmlfiles.extend([os.path.join(subdir, i) for i in subdir_xmlfiles])

        if not catredxmlfiles:
            print(f"Warning: No XML files found in {catred_dir}")
            return pd.DataFrame()

        print(f"Found {len(catredxmlfiles)} CATRED XML files")

        catred_fileinfo: Dict[int, Dict[str, Any]] = {}
        for uid, catredxmlfile in enumerate(catredxmlfiles):
            try:
                catred_fileinfo[uid] = {}
                # Store XML file path
                catred_fileinfo[uid]["xml_file"] = os.path.join(catred_dir, catredxmlfile)

                # Extract tile ID from XML
                mertileid = self.get_xml_element(
                    os.path.join(catred_dir, catredxmlfile), "Data/TileIndex"
                ).text
                catred_fileinfo[uid]["mertileid"] = int(mertileid)

                # Extract FITS file name from XML
                catred_fitsfile = self.get_xml_element(
                    os.path.join(catred_dir, catredxmlfile), "Data/Catalog/DataContainer/FileName"
                ).text
                catred_fileinfo[uid]["fits_file"] = os.path.join(
                    os.path.dirname(catred_fileinfo[uid]["xml_file"]), catred_fitsfile
                )

                # Extract dataset release version from XML
                dataset_release = self.get_xml_element(
                    os.path.join(catred_dir, catredxmlfile), "Header/DataSetRelease"
                ).text
                catred_fileinfo[uid]["dataset_release"] = dataset_release

                # Extract creation date from XML
                creation_date = self.get_xml_element(
                    os.path.join(catred_dir, catredxmlfile), "Header/CreationDate"
                ).text
                catred_fileinfo[uid]["creation_date"] = (
                    datetime.datetime.strptime(creation_date[:-2], "%Y-%m-%dT%H:%M:%S.%f")
                    .date()
                    .isoformat()
                )

                manualvalidationstatus = self.get_xml_element(
                    os.path.join(catred_dir, catredxmlfile), "Header/ManualValidationStatus"
                ).text
                catred_fileinfo[uid]["manual_validation_status"] = manualvalidationstatus

                # Add a column for remarks (empty for now)
                catred_fileinfo[uid]["remarks"] = ""

            except Exception as e:
                print(f"Warning: Failed to process {catredxmlfile}: {e}")
                continue

        if not catred_fileinfo:
            print("Warning: No valid CATRED file information could be extracted")
            return pd.DataFrame()

        # Create DataFrame
        catred_fileinfo_df = pd.DataFrame.from_dict(catred_fileinfo, orient="index")
        catred_fileinfo_df = catred_fileinfo_df[
            [
                "mertileid",
                "dataset_release",
                "creation_date",
                "xml_file",
                "fits_file",
                "manual_validation_status",
                "remarks",
            ]
        ]
        catred_fileinfo_df.index.name = "uid"

        # Handle duplicates:
        # If multiple rows with same mertileid and dataset_release exist, keep only the latest creation_date
        mertileid_valuecounts = catred_fileinfo_df[
            "mertileid"
        ].value_counts()  # count occurrences of each mertileid
        mertileid_valuecounts_mask = mertileid_valuecounts > len(
            catred_fileinfo_df["dataset_release"].unique()
        )  # create mask for mertileids with duplicates across dataset_releases
        duplicate_indices = mertileid_valuecounts[
            mertileid_valuecounts_mask
        ].index  # get the mertileids that are duplicated
        # method 1: loop through duplicates and drop older ones
        # for mertileid in duplicate_indices:
        #     duplicate_rows = catred_fileinfo_df[catred_fileinfo_df['mertileid'] == mertileid]
        #     for dataset_release in duplicate_rows['dataset_release'].unique():
        #         subset = duplicate_rows[duplicate_rows['dataset_release'] == dataset_release]
        #         if len(subset) > 1:
        #             latest_row = subset.loc[subset['creation_date'].idxmax()]
        #             rows_to_drop = subset.index.difference([latest_row.name])
        #             catred_fileinfo_df.drop(rows_to_drop, inplace=True)
        # method 2: groupby and filter
        duplicate_indices_allentries = catred_fileinfo_df[
            catred_fileinfo_df["mertileid"].isin(duplicate_indices)
        ]  # get all entries with duplicate mertileids
        rest = catred_fileinfo_df[
            ~catred_fileinfo_df["mertileid"].isin(duplicate_indices)
        ]  # get all entries without duplicate mertileids
        non_duplicate_combinations = duplicate_indices_allentries.groupby(
            ["mertileid", "dataset_release"]
        ).filter(
            lambda x: len(x) == 1
        )  # get non-duplicated (mertileid, dataset_release) combinations
        duplicate_combinations = duplicate_indices_allentries.groupby(
            ["mertileid", "dataset_release"]
        ).filter(
            lambda x: len(x) > 1
        )  # get duplicated (mertileid, dataset_release) combinations
        if not duplicate_combinations.empty:
            print(
                f"Found {len(duplicate_combinations)} duplicate CATRED entries based on "
                f"(mertileid, dataset_release) combinations. Keeping only latest creation_date entries."
            )
            duplicate_combinations["remarks"] = "duplicate"
            catred_fileinfo_df_wd = pd.concat(
                [rest, non_duplicate_combinations, duplicate_combinations]
            )
            catred_fileinfo_df_wd = catred_fileinfo_df_wd.sort_index(inplace=False)
            catred_fileinfo_df_wd = catred_fileinfo_df_wd.reset_index(drop=True, inplace=False)
            catred_fileinfo_df_wd.index.name = "uid"
            catred_fileinfo_df_wd.index = catred_fileinfo_df_wd.index.astype(int)
            catred_fileinfo_df_wd.to_csv(
                catred_fileinfo_csv.replace(".csv", "_with_duplicates.csv"), index=True
            )
        latest_duplicates_by_creationdate = duplicate_combinations.loc[
            duplicate_combinations.groupby(["mertileid", "dataset_release"])[
                "creation_date"
            ].idxmax()
        ]  # for duplicated combinations, keep only the latest creation_date entry

        # reassemble the dataframe
        catred_fileinfo_df = pd.concat(
            [rest, non_duplicate_combinations, latest_duplicates_by_creationdate]
        )
        catred_fileinfo_df = catred_fileinfo_df.sort_index(inplace=False)
        catred_fileinfo_df = catred_fileinfo_df.reset_index(drop=True, inplace=False)
        catred_fileinfo_df.index.name = "uid"

        # Save the DataFrame to a CSV file
        output_csv = paths["catred_fileinfo_csv"]
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        catred_fileinfo_df.to_csv(output_csv, index=True)
        print(f"Saved catred_fileinfo.csv to {output_csv}")

        return catred_fileinfo_df

    def _generate_catred_polygons(
        self, catred_fileinfo_df: pd.DataFrame, paths: Dict[str, str]
    ) -> pd.DataFrame:
        """Generate catred_polygons_by_tileid.pkl from XML files (based on notebook cells 25-26)."""
        print("Extracting polygons from XML files and saving to catred_fileinfo_df")

        # Import shapely here to avoid import issues if not needed
        try:
            from shapely.geometry import Polygon as ShapelyPolygon
        except ImportError:
            print("Warning: Shapely not available - cannot generate polygon data")
            return catred_fileinfo_df

        def extract_polygon_from_xml(xml_file):
            """Extract polygon from CATRED XML file."""
            try:
                merpolygon = self.get_xml_element(xml_file, "Data/SpatialCoverage/Polygon")
                catred_vertices = []
                vertices = merpolygon.findall("Vertex")
                for vertex in vertices:
                    coords = (float(vertex.find("C1").text), float(vertex.find("C2").text))
                    catred_vertices.append(coords)
                return ShapelyPolygon(catred_vertices)
            except Exception as e:
                print(f"Warning: Failed to extract polygon from {xml_file}: {e}")
                return None

        # Make sure the 'polygon' column exists in the DataFrame
        if "polygon" not in catred_fileinfo_df.columns:
            catred_fileinfo_df["polygon"] = None

        # Apply the function to each row in the DataFrame to populate the 'polygon' column
        catred_fileinfo_df["polygon"] = catred_fileinfo_df["xml_file"].apply(
            extract_polygon_from_xml
        )

        # Remove rows where polygon extraction failed
        initial_count = len(catred_fileinfo_df)
        catred_fileinfo_df = catred_fileinfo_df.dropna(subset=["polygon"])
        final_count = len(catred_fileinfo_df)

        if final_count < initial_count:
            print(f"Warning: {initial_count - final_count} polygons could not be extracted")

        if final_count == 0:
            print("Error: No valid polygons could be extracted")
            return catred_fileinfo_df

        # Make a dict of polygon values and save it to a pickle file
        catred_fileinfo_dict = catred_fileinfo_df[["polygon"]].to_dict(orient="index")
        for key, val in catred_fileinfo_dict.items():
            catred_fileinfo_dict[key] = val[
                "polygon"
            ]  # Extract the ShapelyPolygon object from the dict

        output_pickle = paths["catred_polygon_pkl"]
        os.makedirs(os.path.dirname(output_pickle), exist_ok=True)

        with open(output_pickle, "wb") as f:
            pickle.dump(catred_fileinfo_dict, f)

        print(f"Generated and saved {final_count} catred polygons to {output_pickle}")

        return catred_fileinfo_df

    def _load_effcovmask_info(self, paths: Dict[str, str]) -> pd.DataFrame:
        """Load effective coverage mask file info, generating if not exists (based on notebook cell 29)."""
        effcovmask_fileinfo_csv = paths["effcovmask_fileinfo_csv"]

        # Get effcovmask_dir from config
        if self.config and hasattr(self.config, "effcovmask_dir"):
            effcovmask_dir = self.config.effcovmask_dir
        else:
            # Fallback to rr2_downloads/DpdHealpixEffectiveCoverageVMPZ
            effcovmask_dir = os.path.join(
                os.path.dirname(paths["effcovmask_fileinfo_csv"]), "DpdHealpixEffectiveCoverageVMPZ"
            )

        if not os.path.exists(effcovmask_dir):
            print(f"Warning: Effective coverage mask directory not found at {effcovmask_dir}")
            return pd.DataFrame()

        # Check if CSV file exists
        if os.path.exists(effcovmask_fileinfo_csv):
            print(
                f"effcovmask_fileinfo.csv already exists in {os.path.dirname(effcovmask_fileinfo_csv)}"
            )
            effcovmask_fileinfo_df = pd.read_csv(effcovmask_fileinfo_csv)
            effcovmask_fileinfo_df.set_index("uid", inplace=True)
            try:
                effcovmask_fileinfo_df_wd = pd.read_csv(
                    effcovmask_fileinfo_csv.replace(".csv", "_with_duplicates.csv")
                )
                # Get list of XML files
                effcovxmlfiles = [
                    i
                    for i in os.listdir(effcovmask_dir)
                    if i.endswith(".xml") and "DpdHealpixEffectiveCoverageVMPZ" in i
                ]
                for subdir in os.listdir(effcovmask_dir):
                    subdir_path = os.path.join(effcovmask_dir, subdir)
                    if os.path.isdir(subdir_path):
                        subdir_files = [
                            os.path.join(subdir, f)
                            for f in os.listdir(subdir_path)
                            if f.endswith(".xml") and "DpdHealpixEffectiveCoverageVMPZ" in f
                        ]
                        effcovxmlfiles.extend(subdir_files)
                # Check for mismatch in number of entries
                if len(effcovmask_fileinfo_df_wd) != len(effcovxmlfiles):
                    print(
                        "Warning: Number of entries in effcovmask_fileinfo.csv does not match number of effective coverage XML files. Regenerating."
                    )
                    effcovmask_fileinfo_df = self._generate_effcovmask_fileinfo(paths)
            except FileNotFoundError:
                pass

            print("effcovmask_fileinfo loaded from CSV file")
        else:
            print(f"effcovmask_fileinfo.csv not found at {effcovmask_fileinfo_csv}")
            effcovmask_fileinfo_df = self._generate_effcovmask_fileinfo(paths)

        return effcovmask_fileinfo_df

    def _generate_effcovmask_fileinfo(self, paths: Dict[str, str]) -> pd.DataFrame:
        """Generate effcovmask_fileinfo.csv from XML files (based on notebook cell 29)."""
        print(
            "Processing effective coverage mask XML files to create effcovmask_fileinfo dictionary"
        )

        # Get effcovmask_dir from config
        if self.config and hasattr(self.config, "effcovmask_dir"):
            effcovmask_dir = self.config.effcovmask_dir
        else:
            # Fallback to rr2_downloads/DpdHealpixEffectiveCoverageVMPZ
            effcovmask_dir = os.path.join(
                os.path.dirname(paths["effcovmask_fileinfo_csv"]), "DpdHealpixEffectiveCoverageVMPZ"
            )

        if not os.path.exists(effcovmask_dir):
            print(f"Warning: Effective coverage mask directory not found at {effcovmask_dir}")
            return pd.DataFrame()

        # Get list of XML files (based on notebook: files with 'DpdHealpixEffectiveCoverageVMPZ' in name)
        effcovxmlfiles = [
            i
            for i in os.listdir(effcovmask_dir)
            if i.endswith(".xml") and "DpdHealpixEffectiveCoverageVMPZ" in i
        ]

        # Get xml files from each subdirectory (named for DSR) too
        for subdir in os.listdir(effcovmask_dir):
            subdir_path = os.path.join(effcovmask_dir, subdir)
            if os.path.isdir(subdir_path):
                subdir_files = [
                    os.path.join(subdir, f)
                    for f in os.listdir(subdir_path)
                    if f.endswith(".xml") and "DpdHealpixEffectiveCoverageVMPZ" in f
                ]
                effcovxmlfiles.extend(subdir_files)

        if not effcovxmlfiles:
            print(f"Warning: No effective coverage XML files found in {effcovmask_dir}")
            return pd.DataFrame()

        print(f"Found {len(effcovxmlfiles)} effective coverage XML files")

        effcovmask_fileinfo: Dict[int, Dict[str, Any]] = {}
        for uid, effcovxmlfile in enumerate(effcovxmlfiles):
            try:
                effcovmask_fileinfo[uid] = {}
                effcovmask_fileinfo[uid]["xml_file"] = os.path.join(effcovmask_dir, effcovxmlfile)

                # Extract tile ID from XML (different path than catred)
                mertileid = self.get_xml_element(
                    os.path.join(effcovmask_dir, effcovxmlfile),
                    "Data/EffectiveCoverageMaskHealpixParams/PatchTileList/TileIndexList",
                ).text
                effcovmask_fileinfo[uid]["mertileid"] = int(mertileid)

                # Extract FITS file name from XML (different path than catred)
                effcov_fitsfile = self.get_xml_element(
                    os.path.join(effcovmask_dir, effcovxmlfile),
                    "Data/EffectiveCoverageMaskHealpix/DataContainer/FileName",
                ).text
                effcovmask_fileinfo[uid]["fits_file"] = os.path.join(
                    os.path.dirname(effcovmask_fileinfo[uid]["xml_file"]), effcov_fitsfile
                )

                # Extract dataset release version from XML
                dataset_release = self.get_xml_element(
                    os.path.join(effcovmask_dir, effcovxmlfile), "Header/DataSetRelease"
                ).text
                effcovmask_fileinfo[uid]["dataset_release"] = dataset_release

                # Extract creation date from XML
                creation_date = self.get_xml_element(
                    os.path.join(effcovmask_dir, effcovxmlfile), "Header/CreationDate"
                ).text
                effcovmask_fileinfo[uid]["creation_date"] = (
                    datetime.datetime.strptime(creation_date[:-2], "%Y-%m-%dT%H:%M:%S.%f")
                    .date()
                    .isoformat()
                )

                # Add a column for remarks (empty for now)
                effcovmask_fileinfo[uid]["remarks"] = ""

            except Exception as e:
                print(f"Warning: Failed to process {effcovxmlfile}: {e}")
                continue

        if not effcovmask_fileinfo:
            print("Warning: No valid effective coverage file information could be extracted")
            return pd.DataFrame()

        # Create DataFrame
        effcovmask_fileinfo_df = pd.DataFrame.from_dict(effcovmask_fileinfo, orient="index")
        effcovmask_fileinfo_df = effcovmask_fileinfo_df[
            ["mertileid", "dataset_release", "creation_date", "xml_file", "fits_file", "remarks"]
        ]
        effcovmask_fileinfo_df.index.name = "uid"

        # Handle duplicates:
        # If multiple rows with same mertileid and dataset_release exist, keep only the latest creation_date

        mertileid_valuecounts = effcovmask_fileinfo_df[
            "mertileid"
        ].value_counts()  # count occurrences of each mertileid
        mertileid_valuecounts_mask = mertileid_valuecounts > len(
            effcovmask_fileinfo_df["dataset_release"].unique()
        )  # create mask for mertileids with duplicates across dataset_releases
        duplicate_indices = mertileid_valuecounts[
            mertileid_valuecounts_mask
        ].index  # get the mertileids that are duplicated
        # method: groupby and filter
        duplicate_indices_allentries = effcovmask_fileinfo_df[
            effcovmask_fileinfo_df["mertileid"].isin(duplicate_indices)
        ]  # get all entries with duplicate mertileids
        rest = effcovmask_fileinfo_df[
            ~effcovmask_fileinfo_df["mertileid"].isin(duplicate_indices)
        ]  # get all entries without duplicate mertileids
        non_duplicate_combinations = duplicate_indices_allentries.groupby(
            ["mertileid", "dataset_release"]
        ).filter(
            lambda x: len(x) == 1
        )  # get non-duplicated (mertileid, dataset_release) combinations
        duplicate_combinations = duplicate_indices_allentries.groupby(
            ["mertileid", "dataset_release"]
        ).filter(
            lambda x: len(x) > 1
        )  # get duplicated (mertileid, dataset_release) combinations
        if not duplicate_combinations.empty:
            print(
                f"Found {len(duplicate_combinations)} duplicate effective coverage mask entries based on "
                f"(mertileid, dataset_release) combinations. Keeping only latest creation_date entries."
            )
            duplicate_combinations["remarks"] = "duplicate"
            effcovmask_fileinfo_df_wd = pd.concat(
                [rest, non_duplicate_combinations, duplicate_combinations]
            )
            effcovmask_fileinfo_df_wd = effcovmask_fileinfo_df_wd.sort_index(inplace=False)
            effcovmask_fileinfo_df_wd = effcovmask_fileinfo_df_wd.reset_index(
                drop=True, inplace=False
            )
            effcovmask_fileinfo_df_wd.index.name = "uid"
            effcovmask_fileinfo_df_wd.to_csv(
                paths["effcovmask_fileinfo_csv"].replace(".csv", "_with_duplicates.csv"), index=True
            )
        latest_duplicates_by_creationdate = duplicate_combinations.loc[
            duplicate_combinations.groupby(["mertileid", "dataset_release"])[
                "creation_date"
            ].idxmax()
        ]  # for duplicated combinations, keep only the latest creation_date entry

        # reassemble the dataframe
        effcovmask_fileinfo_df = pd.concat(
            [rest, non_duplicate_combinations, latest_duplicates_by_creationdate]
        )
        effcovmask_fileinfo_df = effcovmask_fileinfo_df.sort_index(inplace=False)
        effcovmask_fileinfo_df = effcovmask_fileinfo_df.reset_index(drop=True, inplace=False)
        effcovmask_fileinfo_df.index.name = "uid"

        print(f"Generated effcovmask_fileinfo for {len(effcovmask_fileinfo_df)} files")

        # Save the DataFrame to a CSV file
        output_csv = paths["effcovmask_fileinfo_csv"]
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        effcovmask_fileinfo_df.to_csv(output_csv, index=True)
        print(f"Saved effcovmask_fileinfo.csv to {output_csv}")

        return effcovmask_fileinfo_df

    def clear_cache(self) -> None:
        """Clear the data cache to free memory."""
        self.data_cache.clear()
        print("Data cache cleared")
        if self.use_disk_cache:
            print("Note: Disk cache still contains data. Use clear_disk_cache() to clear it.")

    def clear_disk_cache(self, key) -> None:
        """Clear disk cache entries.

        Args:
            key: Specific cache key to clear (None = clear all)
        """
        if self.use_disk_cache and self.disk_cache is not None:
            self.disk_cache.clear(key)
        else:
            print("Disk cache not available")

    def get_cache_info(self) -> Dict[str, Any]:
        """Get disk cache information and statistics."""
        if self.use_disk_cache and self.disk_cache is not None:
            return self.disk_cache.get_cache_info()
        else:
            return {"status": "Disk cache not available"}

    def _get_merged_catalog_source_files(self, paths: Dict[str, Any]) -> list:
        """Get list of source files for merged catalog (for cache invalidation)."""
        source_files = []
        if paths.get("use_gluematchcat"):
            if os.path.exists(paths.get("gluematchcat_xml", "")):
                source_files.append(paths["gluematchcat_xml"])
        else:
            for xml_path in paths.get("mergedetcat_xml_files_dict", {}).values():
                if os.path.exists(xml_path):
                    source_files.append(xml_path)
        return source_files

    def _get_tile_data_source_files(self, paths: Dict[str, Any]) -> list:
        """Get list of source files for tile data (for cache invalidation)."""
        source_files = []
        for list_path in paths.get("detfiles_list_files_dict", {}).values():
            if os.path.exists(list_path):
                source_files.append(list_path)
        return source_files

    def get_memory_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get memory usage statistics.

        Returns:
            Dictionary with memory stats or None if memory manager not available
        """
        if self.memory_manager:
            return self.memory_manager.get_memory_stats()
        return None

    def print_memory_report(self) -> None:
        """Print detailed memory and cache usage report."""
        if self.memory_manager:
            self.memory_manager.print_cache_report(self.data_cache)
        else:
            print("Memory manager not available - cannot generate report")

    def clear_memory_cache(self) -> None:
        """Manually clear all in-memory cached data."""
        cleared = len(self.data_cache)
        self.data_cache.clear()
        if self.memory_manager:
            self.memory_manager.access_times.clear()
        print(f"✓ Cleared {cleared} items from memory cache")

    def _get_catred_dir(self, paths: Dict[str, str]) -> str:
        """Get CATRED directory path."""
        if (
            self.config
            and hasattr(self.config, "catred_dir")
            and isinstance(self.config.catred_dir, str)
        ):
            return self.config.catred_dir
        else:
            return os.path.join(
                os.path.dirname(paths.get("catred_fileinfo_csv", "")), "DpdLE3clFullInputCat"
            )

    def get_cached_algorithms(self) -> list:
        """Get list of currently cached algorithms."""
        return list(self.data_cache.keys())
