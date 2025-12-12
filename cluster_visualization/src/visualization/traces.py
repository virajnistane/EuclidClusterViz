"""
Trace creation module for cluster visualization.

This module handles the creation of all Plotly traces including:
- Cluster detection scatter traces (merged and individual tiles)
- Polygon traces (LEV1, CORE, MER tiles)
- CATRED high-resolution data traces
- SNR filtering and data layering
- Trace styling and hover text formatting
"""

import json
from typing import Any, Dict, List, Optional

import numpy as np
import plotly.graph_objs as go

try:
    from cluster_visualization.utils.spatial_index import CATREDSpatialIndex

    SPATIAL_INDEX_AVAILABLE = True
except ImportError:
    print("Warning: Spatial indexing not available - using fallback proximity detection")
    SPATIAL_INDEX_AVAILABLE = False


class TraceCreator:
    """Handles creation of all Plotly traces for cluster visualization."""

    def __init__(self, colors_list=None, colors_list_transparent=None, catred_handler=None):
        """
        Initialize TraceCreator with color schemes and CATRED handler.

        Args:
            colors_list: List of colors for tile traces
            colors_list_transparent: List of transparent colors for polygon fills
            catred_handler: CATRED handler instance for trace caching
        """
        self.colors_list = colors_list or self._get_default_colors()
        self.colors_list_transparent = (
            colors_list_transparent or self._get_default_transparent_colors()
        )
        self.catred_handler = catred_handler

        # For fallback when no CATRED handler is available
        self.current_catred_data = None

        # Spatial index for fast proximity queries
        self.catred_spatial_index = None

    def create_traces(
        self,
        data: Dict[str, Any],
        show_polygons: bool = True,
        show_mer_tiles: bool = False,
        relayout_data: Optional[Dict] = None,
        catred_masked: bool = False,
        manual_catred_data: Optional[Dict] = None,
        catred_box_data: Optional[Dict] = None,
        existing_catred_traces: Optional[List] = None,
        existing_mosaic_traces: Optional[List] = None,
        existing_mask_overlay_traces: Optional[List] = None,
        snr_threshold_lower_pzwav: Optional[float] = None,
        snr_threshold_upper_pzwav: Optional[float] = None,
        snr_threshold_lower_amico: Optional[float] = None,
        snr_threshold_upper_amico: Optional[float] = None,
        z_threshold_lower: Optional[float] = None,
        z_threshold_upper: Optional[float] = None,
        threshold: float = 0.8,
        maglim: Optional[float] = None,
        show_merged_clusters: bool = True,
        matching_clusters: bool = False,
    ) -> List:
        """
        Create all Plotly traces for the visualization.

        Args:
            data: Main data dictionary with cluster and tile information
            show_polygons: Whether to fill polygons or show outlines only
            show_mer_tiles: Whether to show MER tile polygons
            relayout_data: Current zoom/pan state for zoom threshold checking
            catred_masked: CATRED data masked (True) or unmasked (False)
            manual_catred_data: Manually loaded CATRED scatter data
            existing_catred_traces: Existing CATRED traces to preserve
            existing_mosaic_traces: Existing mosaic traces to preserve
            snr_threshold_lower: Lower SNR threshold for filtering
            snr_threshold_upper: Upper SNR threshold for filtering
            threshold: Effective coverage threshold for masked CATRED data (default 0.8)
            maglim: Magnitude limit for CATRED data filtering (default None for no filtering)

        Returns:
            List of Plotly trace objects ready for figure display"""
        traces: List = []  # Polygon traces (bottom layer)

        # Apply SNR filtering to merged data
        # if data['algorithm'] == 'PZWAV':
        #     datamod_detcluster_mergedcat = self._apply_snr_filtering(data['data_detcluster_mergedcat'], algorithm=data['algorithm'],
        #                                                              snr_threshold_lower=snr_threshold_lower_pzwav, snr_threshold_upper=snr_threshold_upper_pzwav)
        # elif data['algorithm'] == 'AMICO':
        #     datamod_detcluster_mergedcat = self._apply_snr_filtering(data['data_detcluster_mergedcat'], algorithm=data['algorithm'],
        #                                                              snr_threshold_lower=snr_threshold_lower_amico, snr_threshold_upper=snr_threshold_upper_amico)

        datamod_detcluster_mergedcat = self._apply_redshift_filtering(
            data["data_detcluster_mergedcat"], z_threshold_lower, z_threshold_upper
        )

        # Check zoom threshold for CATRED data display
        zoom_threshold_met = self._check_zoom_threshold(relayout_data, show_mer_tiles)

        # Get CATRED data points for proximity-based marker enhancement
        catred_points = self._get_catred_data_points(
            manual_catred_data, existing_catred_traces, catred_box_data
        )

        # Create data traces in layered order for proper visual hierarchy
        # Layer order: CATRED (bottom) → Merged clusters → Individual tile clusters (top)
        catred_traces: List = []
        cluster_traces: List = []

        # Add CATRED traces to separate list (bottom layer)
        self._add_existing_catred_traces(catred_traces, existing_catred_traces)
        try:
            assert type(catred_masked) is bool
            self._add_manual_catred_traces(
                catred_traces, show_mer_tiles, catred_masked, manual_catred_data, zoom_threshold_met
            )
        except:
            print(
                "Debug: catred_masked is not a boolean, probably set to 'none' in CATREDCallbacks"
            )
            pass

        try:
            assert type(catred_masked) is bool
            self._add_catred_box_trace(
                catred_traces, show_mer_tiles, catred_masked, catred_box_data
            )
        except:
            print(
                "Debug: catred_masked is not a boolean, probably set to 'none' in CATREDCallbacks"
            )
            pass

        # Add cluster traces to separate list (top layer) - conditionally based on toggle
        if show_merged_clusters:
            self._add_merged_cluster_trace(
                cluster_traces,
                datamod_detcluster_mergedcat,
                data["algorithm"],
                matching_clusters,
                snr_threshold_lower_pzwav=snr_threshold_lower_pzwav,
                snr_threshold_upper_pzwav=snr_threshold_upper_pzwav,
                snr_threshold_lower_amico=snr_threshold_lower_amico,
                snr_threshold_upper_amico=snr_threshold_upper_amico,
                catred_points=catred_points,
                relayout_data=relayout_data,
            )

        # Create tile traces and polygons
        tile_traces = self._create_tile_traces_and_polygons(
            data,
            traces,
            show_polygons,
            show_mer_tiles,
            snr_threshold_lower_pzwav,
            snr_threshold_upper_pzwav,
            snr_threshold_lower_amico,
            snr_threshold_upper_amico,
            z_threshold_lower,
            z_threshold_upper,
            catred_points,
        )

        # Add tile cluster traces to top layer
        cluster_traces.extend(tile_traces)

        # Prepare mosaic traces (preserve existing ones)
        mosaic_traces = existing_mosaic_traces or []
        if mosaic_traces:
            print(f"Debug: Preserving {len(mosaic_traces)} existing mosaic traces in layer order")

        # Prepare mask overlay traces (preserve existing ones)
        mask_overlay_traces = existing_mask_overlay_traces or []
        if mask_overlay_traces:
            print(
                f"Debug: Preserving {len(mask_overlay_traces)} existing mask overlay traces in layer order"
            )

        # Combine in proper layer order: polygons (bottom) → mosaics → CATRED → clusters (top)
        # This ensures cluster traces are always on top of mosaic and CATRED traces
        return traces + mosaic_traces + mask_overlay_traces + catred_traces + cluster_traces

    def _get_catred_data_points(
        self,
        manual_catred_data: Optional[Dict],
        existing_catred_traces: Optional[List],
        catred_box_data: Optional[Dict],
    ) -> Optional[List]:
        """Get all CATRED data points for proximity-based enhancement."""
        all_points = []

        # Clear bounds cache when getting new CATRED data (important for multiple renders)
        if hasattr(self, "_catred_bounds_cache"):
            delattr(self, "_catred_bounds_cache")
            print("Debug: Cleared old CATRED bounds cache for new data")

        # Collect coordinates from manual CATRED data
        if manual_catred_data and manual_catred_data.get("ra"):
            for ra, dec in zip(manual_catred_data["ra"], manual_catred_data["dec"]):
                all_points.append((ra, dec))
            print(f"Debug: Added {len(manual_catred_data['ra'])} points from manual CATRED data")

        # Collect coordinates from existing CATRED traces (passed from cache)
        if existing_catred_traces and len(existing_catred_traces) > 0:
            # CATRED traces exist, keep current stored data
            if hasattr(self, "current_catred_data") and self.current_catred_data:
                for trace_name, catred_data in self.current_catred_data.items():
                    if catred_data and catred_data.get("ra"):
                        for ra, dec in zip(catred_data["ra"], catred_data["dec"]):
                            all_points.append((ra, dec))
                        print(
                            f"Debug: Added {len(catred_data['ra'])} points from existing trace '{trace_name}'"
                        )
        else:
            # No existing CATRED traces - clear stored CATRED data to revert markers
            if hasattr(self, "current_catred_data"):
                self.current_catred_data = None
                print("Debug: CATRED data cleared - reverting marker enhancements")
            # Clear bounds cache as well
            if hasattr(self, "_catred_bounds_cache"):
                delattr(self, "_catred_bounds_cache")

        if catred_box_data and catred_box_data.get("ra"):
            for ra, dec in zip(catred_box_data["ra"], catred_box_data["dec"]):
                all_points.append((ra, dec))
            print(f"Debug: Added {len(catred_box_data['ra'])} points from CATRED box data")

        # If no CATRED data found, return None (no enhancement)
        if not all_points:
            print("Debug: No CATRED data points found - no enhancement will be applied")
            return None

        print(
            f"Debug: Found {len(all_points)} total CATRED data points for proximity-based enhancement"
        )
        return all_points

    def clear_catred_data(self):
        """Explicitly clear stored CATRED data to revert marker enhancements."""
        if hasattr(self, "current_catred_data"):
            self.current_catred_data = None
            print("Debug: TraceCreator CATRED data explicitly cleared")

        # Clear bounds cache as well
        if hasattr(self, "_catred_bounds_cache"):
            delattr(self, "_catred_bounds_cache")
            print("Debug: CATRED bounds cache cleared")
        if hasattr(self, "_subsampled_catred_cache"):
            delattr(self, "_subsampled_catred_cache")
            print("Debug: Subsampled CATRED cache cleared")

    def _get_subsampled_catred_points(self, catred_points: List) -> List:
        """Get subsampled CATRED points for proximity detection, with caching."""
        if not catred_points:
            return catred_points

        # Create a simple hash to detect changes in CATRED data
        catred_hash = hash(str(len(catred_points)) + str(catred_points[0] if catred_points else ""))

        # Check if we have cached subsampled points for this dataset
        if hasattr(self, "_subsampled_catred_cache"):
            cached_hash, cached_points = self._subsampled_catred_cache
            if cached_hash == catred_hash:
                return cached_points

        # For very large datasets, subsample CATRED points for proximity detection
        if len(catred_points) > 20000:  # Lower threshold for better performance
            import numpy as np

            # Use every 5th point for proximity detection to speed up calculation
            sampled_points = catred_points[::5]
            print(
                f"Debug: Subsampled {len(sampled_points)} from {len(catred_points)} CATRED points for proximity"
            )
        else:
            sampled_points = catred_points

        # Cache the result
        self._subsampled_catred_cache = (catred_hash, sampled_points)
        return sampled_points

    def _check_proximity_with_spatial_index(
        self,
        ra_array: np.ndarray,
        dec_array: np.ndarray,
        catred_points: List,
        proximity_threshold: float = 0.1,
    ) -> np.ndarray:
        """
        Check proximity using spatial index for massive speedup.

        Performance: O(N log M) instead of O(N*M) where:
        - N = number of clusters to check
        - M = number of CATRED points

        For 10k clusters × 100k CATRED points:
        - Old: ~1 billion comparisons (~30-60 seconds)
        - New: ~170k tree queries (~0.5-2 seconds)
        - Speedup: 15-120x faster!

        Args:
            ra_array: Cluster RA coordinates
            dec_array: Cluster Dec coordinates
            catred_points: List of [ra, dec] CATRED points
            proximity_threshold: Radius in degrees (default 0.1 = 6 arcmin)

        Returns:
            Boolean mask: True where cluster is near CATRED data
        """
        import time

        start_time = time.time()

        # Build spatial index if not already built or if CATRED data changed
        catred_array = np.array(catred_points)
        catred_hash = hash(tuple(catred_array.flatten()[:1000]))  # Hash first 1000 values

        if (
            self.catred_spatial_index is None
            or not hasattr(self, "_catred_index_hash")
            or self._catred_index_hash != catred_hash
        ):
            print(f"Building spatial index for {len(catred_points):,} CATRED points...")
            self.catred_spatial_index = CATREDSpatialIndex(
                catred_array[:, 0], catred_array[:, 1], subsample_threshold=100000  # RA  # Dec
            )
            self._catred_index_hash = catred_hash

        # Use spatial index for batch proximity check
        is_near = np.zeros(len(ra_array), dtype=bool)

        for i, (ra, dec) in enumerate(zip(ra_array, dec_array)):
            is_near[i] = self.catred_spatial_index.check_proximity_single(
                ra, dec, proximity_threshold
            )

        elapsed = time.time() - start_time
        n_near = np.sum(is_near)
        print(
            f"Proximity check completed: {n_near:,}/{len(ra_array):,} clusters near CATRED data ({elapsed:.2f}s)"
        )

        return is_near

    def _is_point_near_catred_region(
        self, ra: float, dec: float, catred_points: List, proximity_threshold: float = 0.01
    ) -> bool:
        """Check if a point is within proximity threshold of any CATRED data point.

        NOTE: This is the legacy O(N) method. When CATRED data is large (>1000 points),
        use _check_proximity_with_spatial_index() instead for 10-100x speedup.
        """
        if not catred_points:
            return False

        # Get cached subsampled points
        sampled_points = self._get_subsampled_catred_points(catred_points)

        # Create a simple hash of the sampled points to detect changes
        points_to_hash = sampled_points[:100] if len(sampled_points) > 100 else sampled_points
        catred_points_hash = hash(tuple(points_to_hash))

        # Pre-compute CATRED bounds for quick rejection (with validation)
        if (
            not hasattr(self, "_catred_bounds_cache")
            or self._catred_bounds_cache.get("hash") != catred_points_hash
        ):
            import numpy as np

            catred_array = np.array(sampled_points)
            self._catred_bounds_cache = {
                "ra_min": np.min(catred_array[:, 0]) - proximity_threshold,
                "ra_max": np.max(catred_array[:, 0]) + proximity_threshold,
                "dec_min": np.min(catred_array[:, 1]) - proximity_threshold,
                "dec_max": np.max(catred_array[:, 1]) + proximity_threshold,
                "hash": catred_points_hash,
            }
            print(
                f"Debug: CATRED bounds cache created/updated - {len(sampled_points)} sampled points, hash: {catred_points_hash}"
            )

        # Quick bounding box rejection
        bounds = self._catred_bounds_cache
        if not (
            bounds["ra_min"] <= ra <= bounds["ra_max"]
            and bounds["dec_min"] <= dec <= bounds["dec_max"]
        ):
            return False

        # Only do expensive distance calculation if within bounding box (use sampled points)
        for catred_ra, catred_dec in sampled_points:
            distance_sq = (ra - catred_ra) ** 2 + (dec - catred_dec) ** 2
            if distance_sq <= proximity_threshold**2:  # Avoid sqrt
                return True

        return False

    def _apply_snr_filtering(
        self, cluster_data: np.ndarray, snr_lower: Optional[float], snr_upper: Optional[float]
    ) -> np.ndarray:
        """Apply SNR filtering to merged cluster data."""
        if snr_lower is None and snr_upper is None:
            return cluster_data
        elif snr_lower is not None and snr_upper is not None:
            return cluster_data[
                (cluster_data["SNR_CLUSTER"] >= snr_lower)
                & (cluster_data["SNR_CLUSTER"] <= snr_upper)
            ]
        elif snr_upper is not None and snr_lower is None:
            return cluster_data[cluster_data["SNR_CLUSTER"] <= snr_upper]
        elif snr_lower is not None:
            return cluster_data[cluster_data["SNR_CLUSTER"] >= snr_lower]
        else:
            return cluster_data

    def _apply_redshift_filtering(
        self,
        cluster_data: np.ndarray,
        z_threshold_lower: Optional[float],
        z_threshold_upper: Optional[float],
    ) -> np.ndarray:
        """Apply redshift filtering to merged cluster data."""
        if z_threshold_lower is None and z_threshold_upper is None:
            return cluster_data
        elif z_threshold_lower is not None and z_threshold_upper is not None:
            result = cluster_data[
                (cluster_data["Z_CLUSTER"] >= z_threshold_lower)
                & (cluster_data["Z_CLUSTER"] <= z_threshold_upper)
            ]
            return result
        elif z_threshold_upper is not None and z_threshold_lower is None:
            result = cluster_data[cluster_data["Z_CLUSTER"] <= z_threshold_upper]
            return result
        elif z_threshold_lower is not None:
            result = cluster_data[cluster_data["Z_CLUSTER"] >= z_threshold_lower]
            return result
        else:
            return cluster_data

    def _check_zoom_threshold(self, relayout_data: Optional[Dict], show_mer_tiles: bool) -> bool:
        """Check if zoom level meets threshold for CATRED data display (< 2 degrees)."""
        if not relayout_data or not show_mer_tiles:
            print(
                f"Debug: Zoom check skipped - relayout_data: {relayout_data is not None}, show_mer_tiles: {show_mer_tiles}"
            )
            return False

        print(f"Debug: Checking zoom threshold - relayout_data: {relayout_data}")

        # Extract zoom ranges
        ra_range = dec_range = None

        if "xaxis.range[0]" in relayout_data and "xaxis.range[1]" in relayout_data:
            ra_range = abs(relayout_data["xaxis.range[1]"] - relayout_data["xaxis.range[0]"])
        elif "xaxis.range" in relayout_data:
            ra_range = abs(relayout_data["xaxis.range"][1] - relayout_data["xaxis.range"][0])

        if "yaxis.range[0]" in relayout_data and "yaxis.range[1]" in relayout_data:
            dec_range = abs(relayout_data["yaxis.range[1]"] - relayout_data["yaxis.range[0]"])
        elif "yaxis.range" in relayout_data:
            dec_range = abs(relayout_data["yaxis.range"][1] - relayout_data["yaxis.range"][0])

        print(f"Debug: Zoom ranges - RA: {ra_range}, Dec: {dec_range}")

        # Check threshold (< 2 degrees in both dimensions)
        if ra_range is not None and dec_range is not None and ra_range < 2.0 and dec_range < 2.0:
            print(
                f"Debug: Zoom threshold MET! RA: {ra_range:.3f}° < 2°, Dec: {dec_range:.3f}° < 2°"
            )
            return True
        else:
            print(f"Debug: Zoom threshold NOT met. RA: {ra_range}, Dec: {dec_range}")
            return False

    def _add_existing_catred_traces(
        self, data_traces: List, existing_catred_traces: Optional[List]
    ) -> None:
        """Add existing CATRED traces to preserve them across renders."""
        if existing_catred_traces:
            print(
                f"Debug: Adding {len(existing_catred_traces)} existing CATRED traces to bottom layer"
            )
            data_traces.extend(existing_catred_traces)

    def _add_manual_catred_traces(
        self,
        data_traces: List,
        show_mer_tiles: bool,
        catred_masked: bool,
        manual_catred_data: Optional[Dict],
        zoom_threshold_met: bool,
    ) -> None:
        """Add manually loaded CATRED high-resolution data traces."""
        if not (show_mer_tiles and manual_catred_data):
            if show_mer_tiles and zoom_threshold_met:
                print(
                    f"Debug: CATRED scatter conditions met but no manual data provided - use render button"
                )
            else:
                print(
                    f"Debug: CATRED scatter data conditions not met - show_mer_tiles: {show_mer_tiles}, "
                    f"manual_data: {manual_catred_data is not None}"
                )
            return

        if not manual_catred_data.get("ra"):
            print("Debug: No CATRED scatter data available to display")
            return

        print(f"Debug: Using manually loaded CATRED scatter data")
        print(f"Debug: Creating CATRED scatter trace with {len(manual_catred_data['ra'])} points")

        # Generate unique trace name
        trace_count = self.catred_handler.get_traces_count() if self.catred_handler else 1
        mode_label = "Masked" if catred_masked else "Unmasked"
        trace_name = f"CATRED {mode_label} - MER Tile"

        # Create CATRED scatter trace
        # For masked mode, include effective coverage in customdata for client-side filtering
        if catred_masked and "effective_coverage" in manual_catred_data:
            customdata = manual_catred_data["effective_coverage"]
            print(
                f"Debug: Including effective coverage data for client-side filtering, values range: {min(customdata):.3f} to {max(customdata):.3f}"
            )
        else:
            customdata = list(
                range(len(manual_catred_data["ra"]))
            )  # Fallback to index for click tracking

        catred_trace = go.Scattergl(
            x=manual_catred_data["ra"],
            y=manual_catred_data["dec"],
            mode="markers",
            marker=dict(
                size=10,
                symbol="circle",
                color="rgba(100, 100, 100, 0)",
                line=dict(width=2, color="black"),
            ),  #  color='black', opacity=0,
            name=trace_name,
            text=self._format_catred_hover_text(manual_catred_data),
            hoverinfo="text",
            hoverlabel=dict(bgcolor="lightblue", font_size=12, font_family="Arial"),
            showlegend=True,
            customdata=customdata,  # Use coverage data for masked mode, indices for others
        )
        data_traces.append(catred_trace)

        # Store CATRED data for click callbacks in multiple locations for better access
        if not hasattr(self, "current_catred_data") or self.current_catred_data is None:
            self.current_catred_data = {}
        self.current_catred_data[trace_name] = manual_catred_data

        # Also store in CATRED handler if available
        if self.catred_handler:
            if (
                not hasattr(self.catred_handler, "current_catred_data")
                or self.catred_handler.current_catred_data is None
            ):
                self.catred_handler.current_catred_data = {}
            self.catred_handler.current_catred_data[trace_name] = manual_catred_data
            print(f"Debug: Also stored CATRED data in catred_handler")

        print(
            f"Debug: Stored CATRED data for trace '{trace_name}' with {len(manual_catred_data['ra'])} points"
        )
        print(
            f"Debug: PHZ_PDF sample length: {len(manual_catred_data['phz_pdf'][0]) if manual_catred_data['phz_pdf'] else 'No PHZ_PDF data'}"
        )
        print(f"Debug: Current CATRED data keys: {list(self.current_catred_data.keys())}")
        print(f"Debug: TraceCreator.current_catred_data id: {id(self.current_catred_data)}")
        print(f"Debug: Trace name: '{trace_name}'")
        print("Debug: CATRED trace added to TOP LAYER (should be clickable)")
        print("Debug: About to return from _add_manual_catred_traces method")

    def _add_catred_box_trace(
        self,
        data_traces: List,
        show_mer_tiles: bool,
        catred_masked: bool,
        catred_box_data: Optional[Dict],
    ) -> None:
        """Add CATRED bounding box trace if applicable."""
        if not (show_mer_tiles and catred_box_data):
            if show_mer_tiles:
                print(
                    f"Debug: CATRED scatter conditions met but no manual data provided - use render button"
                )
            else:
                print(
                    f"Debug: CATRED scatter data conditions not met - show_mer_tiles: {show_mer_tiles}, "
                    f"catred_box_data: {catred_box_data is not None}"
                )
            return

        if not catred_box_data.get("ra"):
            print("Debug: No CATRED scatter data available to display")
            return

        print(f"Debug: Using loaded CATRED box data")
        print(f"Debug: Creating CATRED scatter trace with {len(catred_box_data['ra'])} points")

        # Generate unique trace name
        trace_count = self.catred_handler.get_traces_count() if self.catred_handler else 1
        mode_label = "Masked" if catred_masked else "Unmasked"
        trace_name = f"CATRED {mode_label} - Boxed"  # Data #{trace_count + 1}

        # Create CATRED scatter trace
        # For masked mode, include effective coverage in customdata for client-side filtering
        if catred_masked and "effective_coverage" in catred_box_data:
            customdata = catred_box_data["effective_coverage"]
            print(
                f"Debug: Including effective coverage data for client-side filtering, values range: {min(customdata):.3f} to {max(customdata):.3f}"
            )
        else:
            customdata = list(
                range(len(catred_box_data["ra"]))
            )  # Fallback to index for click tracking

        # glow_trace = self._create_glow_trace(catred_box_data['ra'], catred_box_data['dec'], size=10, shape='circle', opacity=0.3)
        # data_traces.append(glow_trace)

        catred_trace = go.Scattergl(
            x=catred_box_data["ra"],
            y=catred_box_data["dec"],
            mode="markers",
            marker=dict(
                size=catred_box_data["trace_marker_size"],
                symbol="circle",
                sizemode="diameter",
                color="rgba(100, 100, 100, 0)",
                line=dict(width=2, color=catred_box_data["trace_marker_color"][0]),
            ),  #  color='black', opacity=0,
            name=trace_name,
            text=self._format_catred_hover_text(catred_box_data),
            hoverinfo="text",
            hoverlabel=dict(bgcolor="lightblue", font_size=12, font_family="Arial"),
            showlegend=True,
            customdata=customdata,  # Use coverage data for masked mode, indices for others
        )
        data_traces.append(catred_trace)

        # Store CATRED data for click callbacks in multiple locations for better access
        if not hasattr(self, "current_catred_data") or self.current_catred_data is None:
            self.current_catred_data = {}
        self.current_catred_data[trace_name] = catred_box_data

        # Also store in CATRED handler if available
        if self.catred_handler:
            if (
                not hasattr(self.catred_handler, "current_catred_data")
                or self.catred_handler.current_catred_data is None
            ):
                self.catred_handler.current_catred_data = {}
            self.catred_handler.current_catred_data[trace_name] = catred_box_data
            print(f"Debug: Also stored CATRED data in catred_handler")

        print(
            f"Debug: Stored CATRED data for trace '{trace_name}' with {len(catred_box_data['ra'])} points"
        )
        print(
            f"Debug: PHZ_PDF sample length: {len(catred_box_data['phz_pdf'][0]) if catred_box_data['phz_pdf'] else 'No PHZ_PDF data'}"
        )
        print(f"Debug: Current CATRED data keys: {list(self.current_catred_data.keys())}")
        print(f"Debug: TraceCreator.current_catred_data id: {id(self.current_catred_data)}")
        print(f"Debug: Trace name: '{trace_name}'")
        print("Debug: CATRED trace added to TOP LAYER (should be clickable)")
        print("Debug: About to return from _add_manual_catred_traces method")

    def _format_catred_hover_text(self, catred_data: Dict[str, List]) -> List[str]:
        """Format hover text for CATRED data points."""
        hover_texts = []
        for i, (x, y, p1, p70) in enumerate(
            zip(
                catred_data["ra"],
                catred_data["dec"],
                catred_data["phz_mode_1"],
                catred_data["phz_70_int"],
            )
        ):
            text = (
                f"CATRED Data Point<br>RA: {x:.6f}<br>Dec: {y:.6f}<br>PHZ_MODE_1: {p1:.3f}<br>"
                f'PHZ_MEDIAN: {catred_data["phz_median"][i]:.3f}<br>PHZ_70_INT: {abs(float(p70[1]) - float(p70[0])):.3f}'
            )

            # Add effective coverage if available
            if "effective_coverage" in catred_data and i < len(catred_data["effective_coverage"]):
                coverage = catred_data["effective_coverage"][i]
                text += f"<br>Effective Coverage: {coverage:.3f}"

            hover_texts.append(text)

        return hover_texts

    def _create_glow_trace(
        self,
        x_coords,
        y_coords,
        size: int,
        shape: str = "square",
        opacity: float = 0.3,
        showlegend: bool = False,
        name: str = "",
    ) -> go.Scattergl:
        """Create a glow effect trace for enhanced markers."""
        return go.Scattergl(
            x=x_coords,
            y=y_coords,
            mode="markers",
            marker=dict(
                size=size,  # Size passed from caller
                symbol=shape,  # 'square'
                color="yellow",
                opacity=opacity,  # Semi-transparent for glow effect
                line=dict(width=2, color="yellow"),
            ),
            name=name if name != "" else "Cluster in Proximity",
            showlegend=showlegend,  # Don't show in legend
            hoverinfo="skip",  # Don't show hover for glow layer
            hovertemplate=None,  # Explicitly disable hover template
        )

    def _create_oval_for_cluster_pair(
        self, pzwav_cluster, amico_cluster, color: str = "rgba(0, 255, 0, 0.3)"
    ) -> go.Scatter:
        """
        Create an oval shape connecting a matched PZWAV-AMICO cluster pair.

        Args:
            pzwav_cluster: PZWAV cluster data (numpy record)
            amico_cluster: AMICO cluster data (numpy record or array)
            color: Color for the oval (default: semi-transparent green)

        Returns:
            Plotly Scatter trace representing an oval
        """
        # Extract coordinates
        if len(amico_cluster) == 0:
            print(f"Warning: No matching AMICO cluster found for PZWAV cluster")
            return None

        # Get first match if multiple matches exist
        if hasattr(amico_cluster, "__len__") and len(amico_cluster) > 1:
            amico_cluster = amico_cluster[0]

        ra1 = pzwav_cluster["RIGHT_ASCENSION_CLUSTER"]
        dec1 = pzwav_cluster["DECLINATION_CLUSTER"]

        # Handle both numpy array and single record
        if hasattr(amico_cluster, "__len__") and len(amico_cluster) == 1:
            ra2 = amico_cluster[0]["RIGHT_ASCENSION_CLUSTER"]
            dec2 = amico_cluster[0]["DECLINATION_CLUSTER"]
        else:
            ra2 = amico_cluster["RIGHT_ASCENSION_CLUSTER"]
            dec2 = amico_cluster["DECLINATION_CLUSTER"]

        # Calculate center and semi-axes
        center_ra = (ra1 + ra2) / 2
        center_dec = (dec1 + dec2) / 2

        # Semi-major axis (distance between points / 2) + padding
        distance = np.sqrt((ra2 - ra1) ** 2 + (dec2 - dec1) ** 2)
        semi_major = distance / 2 + 0.01  # Add padding
        semi_minor = semi_major * 0.5  # Make it elliptical

        # Calculate rotation angle
        if ra2 != ra1:
            angle = np.arctan2(dec2 - dec1, ra2 - ra1)
        else:
            angle = np.pi / 2

        # Generate oval points
        theta = np.linspace(0, 2 * np.pi, 100)
        x_oval = semi_major * np.cos(theta)
        y_oval = semi_minor * np.sin(theta)

        # Rotate and translate
        x_rotated = center_ra + x_oval * np.cos(angle) - y_oval * np.sin(angle)
        y_rotated = center_dec + x_oval * np.sin(angle) + y_oval * np.cos(angle)

        # Create oval trace
        oval_trace = go.Scatter(
            x=x_rotated,
            y=y_rotated,
            mode="lines",
            fill="toself",
            fillcolor=color,
            line=dict(color="green", width=1, dash="dot"),
            name="Matched Pair",
            showlegend=False,
            hoverinfo="skip",
            hovertemplate=None,
        )

        return oval_trace

    def _add_merged_cluster_trace(
        self,
        data_traces: List,
        datamod_detcluster_mergedcat: np.ndarray,
        algorithm: str,
        matching_clusters: bool,
        snr_threshold_lower_pzwav: Optional[float] = None,
        snr_threshold_upper_pzwav: Optional[float] = None,
        snr_threshold_lower_amico: Optional[float] = None,
        snr_threshold_upper_amico: Optional[float] = None,
        catred_points: Optional[List] = None,
        relayout_data: Optional[Dict] = None,
    ) -> None:
        """Add merged cluster detection trace with proximity-based enhancement."""

        # Determine symbol based on algorithm
        # Check if data has DET_CODE_NB column (from gluematchcat)
        has_det_code = "DET_CODE_NB" in datamod_detcluster_mergedcat.dtype.names

        if catred_points is None:
            # No CATRED data - create trace(s) with normal markers
            if has_det_code and algorithm == "BOTH":
                # Separate PZWAV and AMICO clusters
                pzwav_mask = datamod_detcluster_mergedcat["DET_CODE_NB"] == 2
                amico_mask = datamod_detcluster_mergedcat["DET_CODE_NB"] == 1

                pzwav_data = datamod_detcluster_mergedcat[pzwav_mask]
                amico_data = datamod_detcluster_mergedcat[amico_mask]

                pzwav_data = self._apply_snr_filtering(
                    pzwav_data, snr_threshold_lower_pzwav, snr_threshold_upper_pzwav
                )
                amico_data = self._apply_snr_filtering(
                    amico_data, snr_threshold_lower_amico, snr_threshold_upper_amico
                )

                if matching_clusters:
                    # Apply matching logic for clusters
                    pzwav_data = pzwav_data[
                        np.logical_not(np.isnan(pzwav_data["CROSS_ID_CLUSTER"]))
                    ]
                    amico_data = amico_data[
                        np.logical_not(np.isnan(amico_data["CROSS_ID_CLUSTER"]))
                    ]

                    # ZOOM-BASED OVAL RENDERING: Only show ovals in current viewport
                    if relayout_data and "xaxis.range[0]" in relayout_data:
                        # Extract zoom window bounds
                        ra_min = min(
                            relayout_data.get("xaxis.range[0]", 0),
                            relayout_data.get("xaxis.range[1]", 360),
                        )
                        ra_max = max(
                            relayout_data.get("xaxis.range[0]", 0),
                            relayout_data.get("xaxis.range[1]", 360),
                        )
                        dec_min = min(
                            relayout_data.get("yaxis.range[0]", -90),
                            relayout_data.get("yaxis.range[1]", 90),
                        )
                        dec_max = max(
                            relayout_data.get("yaxis.range[0]", -90),
                            relayout_data.get("yaxis.range[1]", 90),
                        )

                        # Filter clusters within viewport (use PZWAV positions)
                        in_viewport = (
                            (pzwav_data["RIGHT_ASCENSION_CLUSTER"] >= ra_min)
                            & (pzwav_data["RIGHT_ASCENSION_CLUSTER"] <= ra_max)
                            & (pzwav_data["DECLINATION_CLUSTER"] >= dec_min)
                            & (pzwav_data["DECLINATION_CLUSTER"] <= dec_max)
                        )
                        pzwav_viewport = pzwav_data[in_viewport]

                        print(f"🔍 Zoom-based oval rendering:")
                        print(
                            f"   Viewport: RA [{ra_min:.2f}, {ra_max:.2f}], Dec [{dec_min:.2f}, {dec_max:.2f}]"
                        )
                        print(
                            f"   PZWAV clusters in view: {len(pzwav_viewport)} / {len(pzwav_data)}"
                        )

                        # Create pairs only for visible clusters
                        match_cluster_pairs = [
                            [
                                cluster,
                                amico_data[
                                    amico_data["ID_DET_CLUSTER"] == cluster["CROSS_ID_CLUSTER"]
                                ],
                            ]
                            for cluster in pzwav_viewport
                        ]
                    else:
                        # No zoom info - show all pairs (with safety limit)
                        print(f"⚠️  No zoom window detected - use Re-render button after zooming")
                        match_cluster_pairs = [
                            [
                                cluster,
                                amico_data[
                                    amico_data["ID_DET_CLUSTER"] == cluster["CROSS_ID_CLUSTER"]
                                ],
                            ]
                            for cluster in pzwav_data
                        ]

                    # Safety limit to prevent browser crash
                    MAX_OVALS = 2000  # Increased since we're filtering by viewport
                    num_matches = len(match_cluster_pairs)

                    if num_matches > MAX_OVALS:
                        print(f"⚠️  {num_matches} pairs in viewport is still too many!")
                        print(f"   Limiting to highest SNR {MAX_OVALS} pairs.")
                        print(f"   💡 Tip: Zoom in further or apply SNR/redshift filters")

                        # Filter to highest SNR clusters
                        pzwav_snr = [p["SNR_CLUSTER"] for p, _ in match_cluster_pairs]
                        top_indices = np.argsort(pzwav_snr)[-MAX_OVALS:]
                        match_cluster_pairs = [match_cluster_pairs[i] for i in top_indices]
                        print(
                            f"   ↳ Showing top {len(match_cluster_pairs)} pairs (SNR >= {min([p['SNR_CLUSTER'] for p, _ in match_cluster_pairs]):.2f})"
                        )

                    # Create oval traces for matched pairs
                    if num_matches > 0:
                        print(f"🎯 Creating {len(match_cluster_pairs)} ovals for matched pairs...")

                        created_count = 0
                        for i, (pzwav_cluster, amico_match) in enumerate(match_cluster_pairs):
                            if len(amico_match) > 0:
                                oval_trace = self._create_oval_for_cluster_pair(
                                    pzwav_cluster, amico_match
                                )
                                if oval_trace:
                                    data_traces.append(oval_trace)
                                    created_count += 1

                            # Progress indicator every 500 ovals
                            if (i + 1) % 500 == 0:
                                print(f"   ↳ Progress: {i + 1}/{len(match_cluster_pairs)} ovals...")

                        print(f"   ✓ Created {created_count} oval traces")
                    else:
                        print(f"   ℹ️  No matched pairs in current viewport")

                # PZWAV trace
                if len(pzwav_data) > 0:
                    pzwav_trace = go.Scattergl(
                        x=pzwav_data["RIGHT_ASCENSION_CLUSTER"],
                        y=pzwav_data["DECLINATION_CLUSTER"],
                        mode="markers",
                        marker=dict(
                            size=20, symbol="square-open", line=dict(width=2), color="black"
                        ),
                        name=f"Merged PZWAV",
                        legendgroup="merged_pzwav",
                        showlegend=True,
                        text=[
                            f"merged (PZWAV)<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                            for snr, cz, ra, dec in zip(
                                pzwav_data["SNR_CLUSTER"],
                                pzwav_data["Z_CLUSTER"],
                                pzwav_data["RIGHT_ASCENSION_CLUSTER"],
                                pzwav_data["DECLINATION_CLUSTER"],
                            )
                        ],
                        customdata=[
                            [snr, z, det_code]
                            for snr, z, det_code in zip(
                                pzwav_data["SNR_CLUSTER"],
                                pzwav_data["Z_CLUSTER"],
                                pzwav_data["DET_CODE_NB"],
                            )
                        ],
                        hoverinfo="text",
                        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
                    )
                    data_traces.append(pzwav_trace)

                # AMICO trace
                if len(amico_data) > 0:
                    amico_trace = go.Scattergl(
                        x=amico_data["RIGHT_ASCENSION_CLUSTER"],
                        y=amico_data["DECLINATION_CLUSTER"],
                        mode="markers",
                        marker=dict(
                            size=20, symbol="diamond-open", line=dict(width=2), color="black"
                        ),
                        name=f"Merged AMICO",
                        legendgroup="merged_amico",
                        showlegend=True,
                        text=[
                            f"merged (AMICO)<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                            for snr, cz, ra, dec in zip(
                                amico_data["SNR_CLUSTER"],
                                amico_data["Z_CLUSTER"],
                                amico_data["RIGHT_ASCENSION_CLUSTER"],
                                amico_data["DECLINATION_CLUSTER"],
                            )
                        ],
                        customdata=[
                            [snr, z, det_code]
                            for snr, z, det_code in zip(
                                amico_data["SNR_CLUSTER"],
                                amico_data["Z_CLUSTER"],
                                amico_data["DET_CODE_NB"],
                            )
                        ],
                        hoverinfo="text",
                        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
                    )
                    data_traces.append(amico_trace)
            else:
                # Single algorithm or no DET_CODE_NB column
                symbol = {"amico": "diamond-open", "pzwav": "square-open"}.get(algorithm.lower())

                if algorithm.lower() == "pzwav":
                    datamod_detcluster_mergedcat = self._apply_snr_filtering(
                        datamod_detcluster_mergedcat,
                        snr_threshold_lower_pzwav,
                        snr_threshold_upper_pzwav,
                    )
                elif algorithm.lower() == "amico":
                    datamod_detcluster_mergedcat = self._apply_snr_filtering(
                        datamod_detcluster_mergedcat,
                        snr_threshold_lower_amico,
                        snr_threshold_upper_amico,
                    )

                merged_trace = go.Scattergl(
                    x=datamod_detcluster_mergedcat["RIGHT_ASCENSION_CLUSTER"],
                    y=datamod_detcluster_mergedcat["DECLINATION_CLUSTER"],
                    mode="markers",
                    marker=dict(size=20, symbol=symbol, line=dict(width=2), color="black"),
                    name=f"Merged {algorithm}",
                    text=[
                        f"merged<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                        for snr, cz, ra, dec in zip(
                            datamod_detcluster_mergedcat["SNR_CLUSTER"],
                            datamod_detcluster_mergedcat["Z_CLUSTER"],
                            datamod_detcluster_mergedcat["RIGHT_ASCENSION_CLUSTER"],
                            datamod_detcluster_mergedcat["DECLINATION_CLUSTER"],
                        )
                    ],
                    customdata=[
                        [snr, z, det_code]
                        for snr, z, det_code in zip(
                            datamod_detcluster_mergedcat["SNR_CLUSTER"],
                            datamod_detcluster_mergedcat["Z_CLUSTER"],
                            datamod_detcluster_mergedcat["DET_CODE_NB"]
                            if has_det_code
                            else [2 if algorithm.lower() == "pzwav" else 1]
                            * len(datamod_detcluster_mergedcat),
                        )
                    ],
                    hoverinfo="text",
                    hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
                )
                data_traces.append(merged_trace)
        else:
            # CATRED data present - create separate traces based on proximity to CATRED points
            # Use spatial indexing for 10-100x speedup!
            if SPATIAL_INDEX_AVAILABLE and len(catred_points) > 1000:
                print(
                    f"Using spatial index for proximity detection with {len(catred_points):,} CATRED points"
                )
                near_catred_mask = self._check_proximity_with_spatial_index(
                    datamod_detcluster_mergedcat["RIGHT_ASCENSION_CLUSTER"],
                    datamod_detcluster_mergedcat["DECLINATION_CLUSTER"],
                    catred_points,
                )
            else:
                print(f"Using legacy proximity detection ({len(catred_points):,} CATRED points)")
                near_catred_mask = np.array(
                    [
                        self._is_point_near_catred_region(ra, dec, catred_points)
                        for ra, dec in zip(
                            datamod_detcluster_mergedcat["RIGHT_ASCENSION_CLUSTER"],
                            datamod_detcluster_mergedcat["DECLINATION_CLUSTER"],
                        )
                    ]
                )

            away_from_catred_data = datamod_detcluster_mergedcat[~near_catred_mask]
            near_catred_data = datamod_detcluster_mergedcat[near_catred_mask]

            # Process away from CATRED data
            if len(away_from_catred_data) > 0:
                if has_det_code and algorithm == "BOTH":
                    # Separate PZWAV and AMICO for away_from_catred
                    pzwav_mask_away = away_from_catred_data["DET_CODE_NB"] == 2
                    amico_mask_away = away_from_catred_data["DET_CODE_NB"] == 1

                    pzwav_away = away_from_catred_data[pzwav_mask_away]
                    amico_away = away_from_catred_data[amico_mask_away]

                    pzwav_away = self._apply_snr_filtering(
                        pzwav_away, snr_threshold_lower_pzwav, snr_threshold_upper_pzwav
                    )
                    amico_away = self._apply_snr_filtering(
                        amico_away, snr_threshold_lower_amico, snr_threshold_upper_amico
                    )

                    # PZWAV away trace
                    if len(pzwav_away) > 0:
                        normal_trace_pzwav = go.Scattergl(
                            x=pzwav_away["RIGHT_ASCENSION_CLUSTER"],
                            y=pzwav_away["DECLINATION_CLUSTER"],
                            mode="markers",
                            marker=dict(
                                size=20, symbol="square-open", line=dict(width=2), color="black"
                            ),
                            name=f"PZWAV (Merged)",  # - {len(pzwav_away)} clusters',
                            legendgroup="merged_pzwav",
                            showlegend=True,
                            text=[
                                f"PZWAV (Merged)<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                                for snr, cz, ra, dec in zip(
                                    pzwav_away["SNR_CLUSTER"],
                                    pzwav_away["Z_CLUSTER"],
                                    pzwav_away["RIGHT_ASCENSION_CLUSTER"],
                                    pzwav_away["DECLINATION_CLUSTER"],
                                )
                            ],
                            customdata=[
                                [snr, z, det_code]
                                for snr, z, det_code in zip(
                                    pzwav_away["SNR_CLUSTER"],
                                    pzwav_away["Z_CLUSTER"],
                                    pzwav_away["DET_CODE_NB"],
                                )
                            ],
                            hoverinfo="text",
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
                        )
                        data_traces.append(normal_trace_pzwav)

                    # AMICO away trace
                    if len(amico_away) > 0:
                        normal_trace_amico = go.Scattergl(
                            x=amico_away["RIGHT_ASCENSION_CLUSTER"],
                            y=amico_away["DECLINATION_CLUSTER"],
                            mode="markers",
                            marker=dict(
                                size=20, symbol="diamond-open", line=dict(width=2), color="black"
                            ),
                            name=f"AMICO (Merged)",  # - {len(amico_away)} clusters',
                            legendgroup="merged_amico",
                            showlegend=True,
                            text=[
                                f"AMICO (Merged)<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                                for snr, cz, ra, dec in zip(
                                    amico_away["SNR_CLUSTER"],
                                    amico_away["Z_CLUSTER"],
                                    amico_away["RIGHT_ASCENSION_CLUSTER"],
                                    amico_away["DECLINATION_CLUSTER"],
                                )
                            ],
                            customdata=[
                                [snr, z, det_code]
                                for snr, z, det_code in zip(
                                    amico_away["SNR_CLUSTER"],
                                    amico_away["Z_CLUSTER"],
                                    amico_away["DET_CODE_NB"],
                                )
                            ],
                            hoverinfo="text",
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
                        )
                        data_traces.append(normal_trace_amico)
                else:
                    # Single algorithm
                    symbol = "diamond-open" if algorithm == "AMICO" else "square-open"

                    if algorithm.lower() == "pzwav":
                        away_from_catred_data = self._apply_snr_filtering(
                            away_from_catred_data,
                            snr_threshold_lower_pzwav,
                            snr_threshold_upper_pzwav,
                        )
                    elif algorithm.lower() == "amico":
                        away_from_catred_data = self._apply_snr_filtering(
                            away_from_catred_data,
                            snr_threshold_lower_amico,
                            snr_threshold_upper_amico,
                        )

                    normal_trace = go.Scattergl(
                        x=away_from_catred_data["RIGHT_ASCENSION_CLUSTER"],
                        y=away_from_catred_data["DECLINATION_CLUSTER"],
                        mode="markers",
                        marker=dict(size=20, symbol=symbol, line=dict(width=2), color="black"),
                        name=f"{algorithm} (Merged)",
                        legendgroup=f"merged_{algorithm.lower()}",
                        showlegend=True,
                        text=[
                            f"{algorithm} (Merged)<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                            for snr, cz, ra, dec in zip(
                                away_from_catred_data["SNR_CLUSTER"],
                                away_from_catred_data["Z_CLUSTER"],
                                away_from_catred_data["RIGHT_ASCENSION_CLUSTER"],
                                away_from_catred_data["DECLINATION_CLUSTER"],
                            )
                        ],
                        customdata=[
                            [snr, z, det_code]
                            for snr, z, det_code in zip(
                                away_from_catred_data["SNR_CLUSTER"],
                                away_from_catred_data["Z_CLUSTER"],
                                away_from_catred_data["DET_CODE_NB"]
                                if has_det_code
                                else [2 if algorithm.lower() == "pzwav" else 1]
                                * len(away_from_catred_data),
                            )
                        ],
                        hoverinfo="text",
                        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
                    )
                    data_traces.append(normal_trace)

            # Create trace for markers near CATRED region (enhanced size with highlight)
            if len(near_catred_data) > 0:
                if has_det_code and algorithm == "BOTH":
                    # Separate PZWAV and AMICO for near_catred
                    pzwav_mask_near = near_catred_data["DET_CODE_NB"] == 2
                    amico_mask_near = near_catred_data["DET_CODE_NB"] == 1

                    pzwav_near = near_catred_data[pzwav_mask_near]
                    amico_near = near_catred_data[amico_mask_near]

                    pzwav_near = self._apply_snr_filtering(
                        pzwav_near, snr_threshold_lower_pzwav, snr_threshold_upper_pzwav
                    )
                    amico_near = self._apply_snr_filtering(
                        amico_near, snr_threshold_lower_amico, snr_threshold_upper_amico
                    )

                    # PZWAV enhanced traces
                    if len(pzwav_near) > 0:
                        glow_trace_pzwav = self._create_glow_trace(
                            pzwav_near["RIGHT_ASCENSION_CLUSTER"],
                            pzwav_near["DECLINATION_CLUSTER"],
                            size=28,
                            shape="square",
                            showlegend=False,
                            name="Merged PZWAV (in CATRED region)",
                        )
                        glow_trace_pzwav["legendgroup"] = "merged_pzwav"
                        data_traces.append(glow_trace_pzwav)

                        enhanced_trace_pzwav = go.Scattergl(
                            x=pzwav_near["RIGHT_ASCENSION_CLUSTER"],
                            y=pzwav_near["DECLINATION_CLUSTER"],
                            mode="markers",
                            marker=dict(
                                size=20,
                                symbol="square-open",
                                line=dict(width=3, color="yellow"),
                                color="black",
                                opacity=1.0,
                            ),
                            name=f"PZWAV (Merged, near CATRED) - {len(pzwav_near)} clusters",
                            legendgroup="merged_pzwav",
                            showlegend=False,
                            text=[
                                f"PZWAV (Merged, near CATRED)<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                                for snr, cz, ra, dec in zip(
                                    pzwav_near["SNR_CLUSTER"],
                                    pzwav_near["Z_CLUSTER"],
                                    pzwav_near["RIGHT_ASCENSION_CLUSTER"],
                                    pzwav_near["DECLINATION_CLUSTER"],
                                )
                            ],
                            customdata=[
                                [snr, z, det_code]
                                for snr, z, det_code in zip(
                                    pzwav_near["SNR_CLUSTER"],
                                    pzwav_near["Z_CLUSTER"],
                                    pzwav_near["DET_CODE_NB"],
                                )
                            ],
                            hoverinfo="text",
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
                        )
                        data_traces.append(enhanced_trace_pzwav)

                    # AMICO enhanced traces
                    if len(amico_near) > 0:
                        glow_trace_amico = self._create_glow_trace(
                            amico_near["RIGHT_ASCENSION_CLUSTER"],
                            amico_near["DECLINATION_CLUSTER"],
                            size=28,
                            shape="diamond",
                            showlegend=False,
                            name="Merged AMICO (in CATRED region)",
                        )
                        glow_trace_amico["legendgroup"] = "merged_amico"
                        data_traces.append(glow_trace_amico)

                        enhanced_trace_amico = go.Scattergl(
                            x=amico_near["RIGHT_ASCENSION_CLUSTER"],
                            y=amico_near["DECLINATION_CLUSTER"],
                            mode="markers",
                            marker=dict(
                                size=20,
                                symbol="diamond-open",
                                line=dict(width=3, color="yellow"),
                                color="black",
                                opacity=1.0,
                            ),
                            name=f"AMICO (Merged, near CATRED) - {len(amico_near)} clusters",
                            legendgroup="merged_amico",
                            showlegend=False,
                            text=[
                                f"AMICO (Merged, near CATRED)<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                                for snr, cz, ra, dec in zip(
                                    amico_near["SNR_CLUSTER"],
                                    amico_near["Z_CLUSTER"],
                                    amico_near["RIGHT_ASCENSION_CLUSTER"],
                                    amico_near["DECLINATION_CLUSTER"],
                                )
                            ],
                            customdata=[
                                [snr, z, det_code]
                                for snr, z, det_code in zip(
                                    amico_near["SNR_CLUSTER"],
                                    amico_near["Z_CLUSTER"],
                                    amico_near["DET_CODE_NB"],
                                )
                            ],
                            hoverinfo="text",
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
                        )
                        data_traces.append(enhanced_trace_amico)

                    print(
                        f"Debug: Enhanced {len(pzwav_near)} PZWAV and {len(amico_near)} AMICO merged clusters near MER data"
                    )
                else:
                    # Single algorithm
                    symbol = "diamond-open" if algorithm == "AMICO" else "square-open"
                    glow_shape = "diamond" if algorithm == "AMICO" else "square"

                    if algorithm.lower() == "pzwav":
                        near_catred_data = self._apply_snr_filtering(
                            near_catred_data, snr_threshold_lower_pzwav, snr_threshold_upper_pzwav
                        )
                    elif algorithm.lower() == "amico":
                        near_catred_data = self._apply_snr_filtering(
                            near_catred_data, snr_threshold_lower_amico, snr_threshold_upper_amico
                        )

                    # Add glow effect trace first (background)
                    glow_trace = self._create_glow_trace(
                        near_catred_data["RIGHT_ASCENSION_CLUSTER"],
                        near_catred_data["DECLINATION_CLUSTER"],
                        size=28,
                        shape=glow_shape,
                        showlegend=False,
                        name=f"{algorithm.upper()} (Merged, near CATRED)",
                    )
                    glow_trace["legendgroup"] = f"merged_{algorithm.lower()}"
                    data_traces.append(glow_trace)

                    # Add main enhanced trace (foreground)
                    enhanced_trace = go.Scattergl(
                        x=near_catred_data["RIGHT_ASCENSION_CLUSTER"],
                        y=near_catred_data["DECLINATION_CLUSTER"],
                        mode="markers",
                        marker=dict(
                            size=20,
                            symbol=symbol,
                            line=dict(width=3, color="yellow"),  # Bright yellow highlight
                            color="black",
                            opacity=1.0,
                        ),
                        name=f"{algorithm.upper()} (Merged, near CATRED) - {len(near_catred_data)} clusters",
                        legendgroup=f"merged_{algorithm.lower()}",
                        showlegend=False,
                        text=[
                            f"{algorithm.upper()} (Merged, near CATRED)<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                            for snr, cz, ra, dec in zip(
                                near_catred_data["SNR_CLUSTER"],
                                near_catred_data["Z_CLUSTER"],
                                near_catred_data["RIGHT_ASCENSION_CLUSTER"],
                                near_catred_data["DECLINATION_CLUSTER"],
                            )
                        ],
                        customdata=[
                            [snr, z, det_code]
                            for snr, z, det_code in zip(
                                near_catred_data["SNR_CLUSTER"],
                                near_catred_data["Z_CLUSTER"],
                                near_catred_data["DET_CODE_NB"]
                                if has_det_code
                                else [2 if algorithm.lower() == "pzwav" else 1]
                                * len(near_catred_data),
                            )
                        ],
                        hoverinfo="text",
                        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
                    )
                    data_traces.append(enhanced_trace)

                    print(
                        f"Debug: Enhanced {len(near_catred_data)} merged clusters near MER data, {len(away_from_catred_data)} normal"
                    )

    def _create_tile_traces_and_polygons(
        self,
        data: Dict[str, Any],
        polygon_traces: List,
        show_polygons: bool,
        show_mer_tiles: bool,
        snr_threshold_lower_pzwav: Optional[float],
        snr_threshold_upper_pzwav: Optional[float],
        snr_threshold_lower_amico: Optional[float],
        snr_threshold_upper_amico: Optional[float],
        z_threshold_lower: Optional[float],
        z_threshold_upper: Optional[float],
        catred_points: Optional[List] = None,
    ) -> List:
        """Create individual tile traces with proximity-based enhancement."""
        tile_traces = []

        # Track if we've shown the algorithm legend entry
        shown_algorithm_legend = {"PZWAV": False, "AMICO": False}

        for tile_key, value in data["data_detcluster_by_cltile"].items():
            data_detcluster_by_cltile = value["detfits_data"]

            # Check if DET_CODE_NB exists in tile data
            has_det_code = (
                "DET_CODE_NB" in data_detcluster_by_cltile.dtype.names
                if len(data_detcluster_by_cltile) > 0
                else False
            )

            # Get the original tile ID (for display) and algorithm
            tileid = value.get(
                "tile_id", tile_key
            )  # Fallback to tile_key for backward compatibility
            tile_algorithm = value.get("algorithm", None)

            # Determine symbol based on algorithm
            symbol = "x-thin"  # Default for PZWAV
            if tile_algorithm == "AMICO":
                symbol = "cross-thin"

            # Apply SNR filtering to tile data
            if tile_algorithm == "PZWAV":
                datamod_detcluster_by_cltile = self._apply_snr_filtering(
                    data_detcluster_by_cltile, snr_threshold_lower_pzwav, snr_threshold_upper_pzwav
                )
            elif tile_algorithm == "AMICO":
                datamod_detcluster_by_cltile = self._apply_snr_filtering(
                    data_detcluster_by_cltile, snr_threshold_lower_amico, snr_threshold_upper_amico
                )

            # Apply redshift filtering to tile data
            datamod_detcluster_by_cltile = self._apply_redshift_filtering(
                datamod_detcluster_by_cltile, z_threshold_lower, z_threshold_upper
            )

            # Configure legend behavior for BOTH algorithm case
            if data["algorithm"] == "BOTH" and tile_algorithm:
                # Use legendgroup to organize by algorithm
                legend_group = f"{tile_algorithm}_cltile_{tileid}"
                # Only show first trace of each algorithm in legend
                show_in_legend = True  # not shown_algorithm_legend[tile_algorithm]
                shown_algorithm_legend[tile_algorithm] = True
                trace_name = f"{tile_algorithm} CL-Tile {tileid}"  # f"{tile_algorithm} Tiles"
            else:
                # Single algorithm mode - show each tile separately
                legend_group = f"{tile_algorithm}_cltile_{tileid}"
                show_in_legend = True
                trace_name = f"{tile_algorithm} CL-Tile {tileid}"

            if catred_points is None:
                # No CATRED data - create single trace with normal markers
                tile_trace = go.Scattergl(
                    x=datamod_detcluster_by_cltile["RIGHT_ASCENSION_CLUSTER"],
                    y=datamod_detcluster_by_cltile["DECLINATION_CLUSTER"],
                    mode="markers",
                    marker=dict(
                        size=10,
                        opacity=1,
                        symbol=symbol,
                        line=dict(width=2, color=self.colors_list[int(tileid)]),
                    ),
                    name=trace_name,
                    legendgroup=legend_group,
                    showlegend=show_in_legend,
                    text=[
                        f"TileID: {tileid}{f' ({tile_algorithm})' if tile_algorithm and data['algorithm'] == 'BOTH' else ''}<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                        for snr, cz, ra, dec in zip(
                            datamod_detcluster_by_cltile["SNR_CLUSTER"],
                            datamod_detcluster_by_cltile["Z_CLUSTER"],
                            datamod_detcluster_by_cltile["RIGHT_ASCENSION_CLUSTER"],
                            datamod_detcluster_by_cltile["DECLINATION_CLUSTER"],
                        )
                    ],
                    customdata=[
                        [snr, z, det_code]
                        for snr, z, det_code in zip(
                            datamod_detcluster_by_cltile["SNR_CLUSTER"],
                            datamod_detcluster_by_cltile["Z_CLUSTER"],
                            datamod_detcluster_by_cltile["DET_CODE_NB"]
                            if has_det_code
                            else [2 if tile_algorithm == "PZWAV" else 1]
                            * len(datamod_detcluster_by_cltile),
                        )
                    ],
                    hoverinfo="text",
                    hoverlabel=dict(bgcolor="lightyellow", font_size=12, font_family="Arial"),
                )
                tile_traces.append(tile_trace)
            else:
                # CATRED data present - create separate traces based on proximity to CATRED points
                if SPATIAL_INDEX_AVAILABLE and len(catred_points) > 1000:
                    print(
                        f"Using spatial index for proximity detection with {len(catred_points):,} CATRED points"
                    )
                    near_catred_mask = self._check_proximity_with_spatial_index(
                        datamod_detcluster_by_cltile["RIGHT_ASCENSION_CLUSTER"],
                        datamod_detcluster_by_cltile["DECLINATION_CLUSTER"],
                        catred_points,
                    )
                else:
                    print(
                        f"Using legacy proximity detection ({len(catred_points):,} CATRED points)"
                    )
                    near_catred_mask = np.array(
                        [
                            self._is_point_near_catred_region(ra, dec, catred_points)
                            for ra, dec in zip(
                                datamod_detcluster_by_cltile["RIGHT_ASCENSION_CLUSTER"],
                                datamod_detcluster_by_cltile["DECLINATION_CLUSTER"],
                            )
                        ]
                    )

                away_from_catred_data = datamod_detcluster_by_cltile[~near_catred_mask]
                near_catred_data = datamod_detcluster_by_cltile[near_catred_mask]

                # Create trace for markers away from CATRED region (normal size)
                if len(away_from_catred_data) > 0:
                    normal_trace = go.Scattergl(
                        x=away_from_catred_data["RIGHT_ASCENSION_CLUSTER"],
                        y=away_from_catred_data["DECLINATION_CLUSTER"],
                        mode="markers",
                        marker=dict(
                            size=10,
                            opacity=1,
                            symbol=symbol,
                            line=dict(width=2, color=self.colors_list[int(tileid)]),
                        ),
                        name=trace_name,
                        legendgroup=legend_group,
                        showlegend=show_in_legend,
                        text=[
                            f"TileID: {tileid}{f' ({tile_algorithm})' if tile_algorithm and data['algorithm'] == 'BOTH' else ''}<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                            for snr, cz, ra, dec in zip(
                                away_from_catred_data["SNR_CLUSTER"],
                                away_from_catred_data["Z_CLUSTER"],
                                away_from_catred_data["RIGHT_ASCENSION_CLUSTER"],
                                away_from_catred_data["DECLINATION_CLUSTER"],
                            )
                        ],
                        customdata=[
                            [snr, z, det_code]
                            for snr, z, det_code in zip(
                                away_from_catred_data["SNR_CLUSTER"],
                                away_from_catred_data["Z_CLUSTER"],
                                away_from_catred_data["DET_CODE_NB"]
                                if has_det_code
                                else [2 if tile_algorithm == "PZWAV" else 1]
                                * len(away_from_catred_data),
                            )
                        ],
                        hoverinfo="text",
                        hoverlabel=dict(bgcolor="lightyellow", font_size=12, font_family="Arial"),
                    )
                    tile_traces.append(normal_trace)

                # Create trace for markers near CATRED region (enhanced size with highlight)
                if len(near_catred_data) > 0:
                    # Add glow effect trace first (background) - use square for PZWAV, diamond for AMICO
                    glow_shape = "square" if tile_algorithm == "PZWAV" else "diamond"
                    glow_trace = self._create_glow_trace(
                        near_catred_data["RIGHT_ASCENSION_CLUSTER"],
                        near_catred_data["DECLINATION_CLUSTER"],
                        20,
                        shape=glow_shape,
                        showlegend=False,
                        name=f"{tile_algorithm.upper()} CL-Tile {tileid} (near CATRED)",
                    )
                    glow_trace["legendgroup"] = legend_group  # f'enhanced_{tile_algorithm.lower()}'
                    tile_traces.append(glow_trace)

                    # Add main enhanced trace (foreground)
                    enhanced_trace = go.Scattergl(
                        x=near_catred_data["RIGHT_ASCENSION_CLUSTER"],
                        y=near_catred_data["DECLINATION_CLUSTER"],
                        mode="markers",
                        marker=dict(
                            size=10,
                            opacity=1,
                            symbol=symbol,
                            # color=self.colors_list[int(tileid)],
                            line=dict(
                                width=2, color=self.colors_list[int(tileid)]
                            ),  # Yellow highlight for 'x' symbols
                        ),
                        name=f"{tile_algorithm} CL-Tile {tileid} (near CATRED) - {len(near_catred_data)} clusters",
                        legendgroup=legend_group,
                        showlegend=False,  # Never show enhanced traces in legend to avoid clutter
                        text=[
                            f"TileID: {tileid}{f' ({tile_algorithm})' if tile_algorithm and data['algorithm'] == 'BOTH' else ''} (enhanced)<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                            for snr, cz, ra, dec in zip(
                                near_catred_data["SNR_CLUSTER"],
                                near_catred_data["Z_CLUSTER"],
                                near_catred_data["RIGHT_ASCENSION_CLUSTER"],
                                near_catred_data["DECLINATION_CLUSTER"],
                            )
                        ],
                        customdata=[
                            [snr, z, det_code]
                            for snr, z, det_code in zip(
                                near_catred_data["SNR_CLUSTER"],
                                near_catred_data["Z_CLUSTER"],
                                near_catred_data["DET_CODE_NB"]
                                if has_det_code
                                else [2 if tile_algorithm == "PZWAV" else 1]
                                * len(near_catred_data),
                            )
                        ],
                        hoverinfo="text",
                        hoverlabel=dict(bgcolor="lightyellow", font_size=12, font_family="Arial"),
                    )
                    tile_traces.append(enhanced_trace)

                    print(
                        f"Debug: Tile {tileid} - Enhanced {len(near_catred_data)} markers near CATRED data, {len(away_from_catred_data)} normal"
                    )

            # Create polygon traces for this tile

            # Create polygon traces for this tile
            self._create_cltile_polygons(
                polygon_traces, data, tileid, value, show_polygons, show_mer_tiles, legendgroup=None
            )

        return tile_traces

    def _create_cltile_polygons(
        self,
        polygon_traces: List,
        data: Dict[str, Any],
        tileid: str,
        tile_value: Dict[str, Any],
        show_polygons: bool,
        show_mer_tiles: bool,
        legendgroup: str = None,
    ) -> None:
        """Create polygon traces for a single tile (LEV1, CORE, and optionally MER)."""
        # Load tile definition
        with open(tile_value["cltiledef_file"], "r") as f:
            tile = json.load(f)

        # LEV1 polygon (always outline)
        lev1_polygon = tile["LEV1"]["POLYGON"][0]
        lev1_x = [p[0] for p in lev1_polygon] + [lev1_polygon[0][0]]
        lev1_y = [p[1] for p in lev1_polygon] + [lev1_polygon[0][1]]

        lev1_trace = go.Scatter(
            x=lev1_x,
            y=lev1_y,
            mode="lines",
            line=dict(width=4, color=self.colors_list[int(tileid)], dash="dash"),
            name=f"Tile {tileid} LEV1",
            # legendgroup=legendgroup if legendgroup is not None else f'cl_tile_{tileid}',
            showlegend=False,
            text=f"Tile {tileid} - LEV1 Polygon",
            hoverinfo="text",
        )
        polygon_traces.append(lev1_trace)

        # CORE polygon (outline + optional fill)
        core_polygon = tile["CORE"]["POLYGON"][0]
        core_x = [p[0] for p in core_polygon] + [core_polygon[0][0]]
        core_y = [p[1] for p in core_polygon] + [core_polygon[0][1]]

        # Configure fill based on show_polygons setting
        if show_polygons:
            fillcolor = self.colors_list_transparent[int(tileid)]
            fill = "toself"
        else:
            fillcolor = None
            fill = None

        core_trace = go.Scatter(
            x=core_x,
            y=core_y,
            fill=fill,
            fillcolor=fillcolor,
            mode="lines",
            line=dict(width=4, color=self.colors_list[int(tileid)]),
            name=f"Tile {tileid} CORE",
            # legendgroup=legendgroup if legendgroup is not None else f'cl_tile_{tileid}',
            showlegend=False,
            text=f"Tile {tileid} - CORE Polygon",
            hoverinfo="text",
        )
        polygon_traces.append(core_trace)

        # MER tile polygons (only when in outline mode and MER tiles requested)
        if (
            show_mer_tiles
            and not show_polygons
            and not data["catred_info"].empty
            and "polygon" in data["catred_info"].columns
        ):
            self._create_mer_tile_polygons(
                polygon_traces,
                data,
                tile,
                tileid,
                legendgroup=legendgroup if legendgroup is not None else f"cl_tile_{tileid}",
            )

    def _create_mer_tile_polygons(
        self,
        polygon_traces: List,
        data: Dict[str, Any],
        tile: Dict[str, Any],
        tileid: str,
        legendgroup: str = None,
    ) -> None:
        """Create MER tile polygon traces for a cluster tile."""
        for mertileid in tile["LEV1"]["ID_INTERSECTED"]:
            if mertileid in data["catred_info"]["mertileid"].values:
                merpoly = (
                    data["catred_info"]
                    .loc[
                        (data["catred_info"]["mertileid"] == mertileid)
                        & (data["catred_info"]["dataset_release"] == data["catred_dsr"])
                    ]
                    .squeeze()["polygon"]
                )
                try:
                    if merpoly is not None:
                        x, y = merpoly.exterior.xy
                        mertile_trace = go.Scatter(
                            x=list(x),
                            y=list(y),
                            fill="toself",
                            fillcolor=self.colors_list_transparent[int(tileid)],
                            mode="lines",
                            line=dict(width=2, color=self.colors_list[int(tileid)], dash="dot"),
                            name=f"MER-Tile {mertileid}",
                            # legendgroup=legendgroup if legendgroup is not None else None,
                            showlegend=False,
                            text=f"MER-Tile {mertileid} - CL-Tile {tileid}",
                            hoverinfo="text",
                            hoveron="fills+points",
                        )
                        polygon_traces.append(mertile_trace)
                except Exception as e:
                    print(f"Debug: merpoly = {merpoly}, type={type(merpoly)}")

    def _get_default_colors(self) -> List[str]:
        """Get default color list for tile traces."""
        return [
            "red",
            "blue",
            "green",
            "orange",
            "purple",
            "brown",
            "pink",
            "gray",
            "olive",
            "cyan",
            "magenta",
            "yellow",
            "darkred",
            "darkblue",
            "darkgreen",
        ] * 10  # Repeat to handle many tiles

    def _get_default_transparent_colors(self) -> List[str]:
        """Get default transparent color list for polygon fills."""
        # Map CSS color names to RGBA with 0.3 opacity
        color_map = {
            "red": "rgba(255, 0, 0, 0.2)",
            "blue": "rgba(0, 0, 255, 0.2)",
            "green": "rgba(0, 128, 0, 0.2)",
            "orange": "rgba(255, 165, 0, 0.2)",
            "purple": "rgba(128, 0, 128, 0.2)",
            "brown": "rgba(165, 42, 42, 0.2)",
            "pink": "rgba(255, 192, 203, 0.2)",
            "gray": "rgba(128, 128, 128, 0.2)",
            "olive": "rgba(128, 128, 0, 0.2)",
            "cyan": "rgba(0, 255, 255, 0.2)",
            "magenta": "rgba(255, 0, 255, 0.2)",
            "yellow": "rgba(255, 255, 0, 0.2)",
            "darkred": "rgba(139, 0, 0, 0.2)",
            "darkblue": "rgba(0, 0, 139, 0.2)",
            "darkgreen": "rgba(0, 100, 0, 0.2)",
        }
        base_colors = self._get_default_colors()
        return [color_map.get(color, f"rgba(128, 128, 128, 0.2)") for color in base_colors]
