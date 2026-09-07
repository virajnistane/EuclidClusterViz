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
import time
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union, cast
from numpy.typing import NDArray

import numpy as np
import plotly.graph_objs as go

from cluster_visualization.src.visualization.catred_proximity import (
    CatredProximityDetector,
    create_glow_trace,
)
from cluster_visualization.utils.profiler import TraceProfiler

StructuredArray = NDArray[np.void]

class TraceCreator:
    """Handles creation of all Plotly traces for cluster visualization."""

    def __init__(
        self, colors_list=None, colors_list_transparent=None, catred_handler=None, ned_handler=None
    ):
        """
        Initialize TraceCreator with color schemes and CATRED handler.

        Args:
            colors_list: List of colors for tile traces
            colors_list_transparent: List of transparent colors for polygon fills
            catred_handler: CATRED handler instance for trace caching
            ned_handler: NEDHandler instance for spec-z cluster filtering (optional)
        """
        self.colors_list = colors_list or self._get_default_colors()
        self.colors_list_transparent = (
            colors_list_transparent or self._get_default_transparent_colors()
        )
        self.catred_handler = catred_handler
        self.ned_handler = ned_handler

        # Proximity detection state (spatial index + caches) lives here
        self.proximity_detector = CatredProximityDetector()

        # For fallback when no CATRED handler is available
        self.current_catred_data = None

        # Tile definition cache: path -> parsed JSON (avoids repeated disk reads per render)
        self._tile_def_cache: Dict[str, Any] = {}

        # Performance profiler (set CLUSTERVIZ_PROFILE=0 to disable)
        self._profiler = TraceProfiler()

        # Per-row tile colours / richness strings of the merged catalog being rendered.
        # Set by create_cluster_traces for the duration of one build (see _row_cache_for).
        self._active_rows: Optional[Dict[str, Any]] = None

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
        existing_ned_specz_traces: Optional[List] = None,
        existing_ned_nearby_catred_traces: Optional[List] = None,
        snr_threshold_lower_pzwav: Optional[float] = None,
        snr_threshold_upper_pzwav: Optional[float] = None,
        snr_threshold_lower_amico: Optional[float] = None,
        snr_threshold_upper_amico: Optional[float] = None,
        snr_include_missing_pzwav: bool = True,
        snr_include_missing_amico: bool = True,
        z_threshold_lower: Optional[float] = None,
        z_threshold_upper: Optional[float] = None,
        z_include_missing: bool = True,
        richness_threshold_lower: Optional[float] = None,
        richness_threshold_upper: Optional[float] = None,
        richness_mode: Optional[str] = None,
        richness_include_missing: bool = True,
        flag_quality_zp: Optional[List[int]] = None,
        flag_quality_rs: Optional[List[int]] = None,
        idcluster_list: Optional[List[int]] = None,
        ned_specz_filter: bool = False,
        angular_tolerance: float = 2.0,
        z_tolerance: float = 0.02,
        threshold: float = 0.8,
        maglim: Optional[float] = None,
        show_unmerged_clusters: bool = False,
        matching_clusters: bool = False,
        show_cltile_info: bool = True,
        view_bounds: Optional[Tuple[float, float, float, float]] = None,
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
        _t_create = time.perf_counter()

        # Check zoom threshold for CATRED data display
        zoom_threshold_met = self._check_zoom_threshold(relayout_data, show_mer_tiles)

        # Get CATRED data points for proximity-based marker enhancement
        catred_points = self._get_catred_data_points(
            manual_catred_data, existing_catred_traces, catred_box_data
        )

        # Create data traces in layered order for proper visual hierarchy
        # Layer order: CATRED (bottom) → Merged clusters → Individual tile clusters (top)
        catred_traces: List = []

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

        # Filter-dependent cluster traces (merged, matched-pair ovals, unmerged) - top layer
        cluster_traces = self.create_cluster_traces(
            data,
            relayout_data=relayout_data,
            catred_points=catred_points,
            snr_threshold_lower_pzwav=snr_threshold_lower_pzwav,
            snr_threshold_upper_pzwav=snr_threshold_upper_pzwav,
            snr_threshold_lower_amico=snr_threshold_lower_amico,
            snr_threshold_upper_amico=snr_threshold_upper_amico,
            snr_include_missing_pzwav=snr_include_missing_pzwav,
            snr_include_missing_amico=snr_include_missing_amico,
            z_threshold_lower=z_threshold_lower,
            z_threshold_upper=z_threshold_upper,
            z_include_missing=z_include_missing,
            richness_threshold_lower=richness_threshold_lower,
            richness_threshold_upper=richness_threshold_upper,
            richness_mode=richness_mode,
            richness_include_missing=richness_include_missing,
            flag_quality_zp=flag_quality_zp,
            flag_quality_rs=flag_quality_rs,
            idcluster_list=idcluster_list,
            ned_specz_filter=ned_specz_filter,
            show_unmerged_clusters=show_unmerged_clusters,
            matching_clusters=matching_clusters,
            show_cltile_info=show_cltile_info,
            view_bounds=view_bounds,
        )

        # Create CL-tile polygons (filter-independent), merged into a few traces
        tile_polygons: List = []
        for tile_key, value in data["data_detcluster_by_cltile"].items():
            tileid = value.get("tile_id", tile_key)
            self._create_cltile_polygons(
                tile_polygons, data, tileid, value, show_polygons, show_mer_tiles, legendgroup=None
            )
        traces.extend(self._merge_polygon_traces(tile_polygons))

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

        # Prepare NED spec-z traces (preserve existing ones)
        ned_specz_traces = existing_ned_specz_traces or []
        if ned_specz_traces:
            print(f"Debug: Preserving {len(ned_specz_traces)} existing NED spec-z traces in layer order")

        # Prepare NED-nearby CATRED traces (preserve existing ones)
        ned_nearby_catred_traces = existing_ned_nearby_catred_traces or []
        if ned_nearby_catred_traces:
            print(
                f"Debug: Preserving {len(ned_nearby_catred_traces)} existing NED-nearby CATRED traces in layer order"
            )

        # Combine in proper layer order: polygons (bottom) → mosaics → CATRED → clusters (top)
        # This ensures cluster traces are always on top of mosaic and CATRED traces

        # Persist current_catred_data to shared diskcache AFTER both _add_manual_catred_traces
        # and _add_catred_box_trace have run, so the cache always has the full picture
        # (tile data + box data). The background callback worker writes here; the main-process
        # PHZ click callback reads it back via the diskcache fallback.
        if hasattr(self, "current_catred_data") and self.current_catred_data:
            _t = time.perf_counter()
            try:
                import diskcache as _dc
                import os as _os
                _state_dir = _os.path.join(_os.path.expanduser("~"), ".cache", "clusterviz_state")
                with _dc.Cache(_state_dir) as _sc:
                    _sc.set("catred_click_data", self.current_catred_data)
                print(f"Debug: Persisted {len(self.current_catred_data)} CATRED trace(s) to state cache "
                      f"(keys: {list(self.current_catred_data.keys())})")
            except Exception as _exc:
                print(f"Warning: Could not persist CATRED data to state cache: {_exc}")
            self._profiler.record("create_traces:diskcache", time.perf_counter() - _t)

        _result = (
            traces
            + mosaic_traces
            + mask_overlay_traces
            + catred_traces
            + ned_specz_traces
            + ned_nearby_catred_traces
            + cluster_traces
        )
        self._profiler.record("create_traces:total", time.perf_counter() - _t_create)
        self._profiler.tick_render()
        return _result

    VIEW_MARGIN = 1.0  # fraction of the view added on each side when culling (keep in sync with ui_callbacks)

    # Sky map culling settings; set from config.ini [view] by configure_view() at startup
    VIEW_SETTINGS = {"cull_min_clusters": 5000, "max_points_sent": 50000, "density_threshold": 50000}

    @classmethod
    def configure_view(cls, cull_min_clusters=None, max_points_sent=None, density_threshold=None):
        """Set the [view] settings (None keeps the current value)."""
        for key, value in (
            ("cull_min_clusters", cull_min_clusters),
            ("max_points_sent", max_points_sent),
            ("density_threshold", density_threshold),
        ):
            if value is not None:
                cls.VIEW_SETTINGS[key] = int(value)

    @classmethod
    def max_points_sent(cls) -> int:
        """Most clusters sent per request; the margin around the view shrinks to fit."""
        return cls.VIEW_SETTINGS["max_points_sent"]

    @classmethod
    def density_threshold(cls) -> int:
        """Above this many clusters in the visible area, a density grid replaces markers."""
        return cls.VIEW_SETTINGS["density_threshold"]

    @classmethod
    def cull_min_clusters(cls) -> int:
        """Catalogs at or below this size are sent whole (no culling)."""
        return cls.VIEW_SETTINGS["cull_min_clusters"]

    # Margins tried in turn until the clusters fit the point budget (see create_cluster_traces)
    CULL_MARGINS = (VIEW_MARGIN, 0.25, 0.0)

    # Density grid colours (2-D map and globe)
    DENSITY_COLORSCALE = [[0, "rgba(43,87,151,0.15)"], [1, "rgba(43,87,151,0.95)"]]

    @classmethod
    def _cull_to_view(cls, arr: np.ndarray, view_bounds, margin: Optional[float] = None) -> np.ndarray:
        """Rows within the view (plus margin, a fraction of the view on each side; default
        VIEW_MARGIN). RA is compared modulo 360° around the view centre, so a field
        crossing RA 0°/360° keeps the right clusters."""
        if arr is None or len(arr) == 0:
            return arr
        return arr[cls._cull_mask(arr, view_bounds, margin)]

    @classmethod
    def _cull_mask(cls, arr: np.ndarray, view_bounds, margin: Optional[float] = None) -> np.ndarray:
        """Boolean mask behind _cull_to_view (cheap to count; no row copies)."""
        margin = cls.VIEW_MARGIN if margin is None else margin
        ra_min, ra_max, dec_min, dec_max = view_bounds
        ra_lo, ra_hi = sorted((float(ra_min), float(ra_max)))
        dec_lo, dec_hi = sorted((float(dec_min), float(dec_max)))
        half_ra = (ra_hi - ra_lo) / 2 * (1 + 2 * margin)
        pad_dec = (dec_hi - dec_lo) * margin
        centre = (ra_lo + ra_hi) / 2
        ra = np.asarray(arr["RIGHT_ASCENSION_CLUSTER"], dtype=float)
        dec = np.asarray(arr["DECLINATION_CLUSTER"], dtype=float)
        d_ra = (ra - centre + 180.0) % 360.0 - 180.0
        return (np.abs(d_ra) <= half_ra) & (dec >= dec_lo - pad_dec) & (dec <= dec_hi + pad_dec)

    def _density_trace(self, arr: np.ndarray, view_bounds, bins: int = 120):
        """Cluster counts on a grid over the view (empty cells transparent)."""
        ra_lo, ra_hi = sorted((float(view_bounds[0]), float(view_bounds[1])))
        dec_lo, dec_hi = sorted((float(view_bounds[2]), float(view_bounds[3])))
        pad_ra = (ra_hi - ra_lo) * self.VIEW_MARGIN
        pad_dec = (dec_hi - dec_lo) * self.VIEW_MARGIN
        counts, xedges, yedges = np.histogram2d(
            np.asarray(arr["RIGHT_ASCENSION_CLUSTER"], dtype=float),
            np.asarray(arr["DECLINATION_CLUSTER"], dtype=float),
            bins=bins,
            range=[[ra_lo - pad_ra, ra_hi + pad_ra], [dec_lo - pad_dec, dec_hi + pad_dec]],
        )
        z = counts.T.astype(float)
        z[z == 0] = np.nan
        return go.Heatmap(
            x=(xedges[:-1] + xedges[1:]) / 2,
            y=(yedges[:-1] + yedges[1:]) / 2,
            z=z,
            name="Merged clusters (density)",
            colorscale=self.DENSITY_COLORSCALE,
            colorbar=dict(title=dict(text="Clusters"), thickness=10, len=0.5),
            hovertemplate="RA %{x:.2f}°, Dec %{y:.2f}°<br>%{z:.0f} clusters<extra>Zoom in for individual clusters</extra>",
            showscale=True,
        )

    def create_cluster_traces(
        self,
        data: Dict[str, Any],
        relayout_data: Optional[Dict] = None,
        catred_points: Optional[List] = None,
        snr_threshold_lower_pzwav: Optional[float] = None,
        snr_threshold_upper_pzwav: Optional[float] = None,
        snr_threshold_lower_amico: Optional[float] = None,
        snr_threshold_upper_amico: Optional[float] = None,
        snr_include_missing_pzwav: bool = True,
        snr_include_missing_amico: bool = True,
        z_threshold_lower: Optional[float] = None,
        z_threshold_upper: Optional[float] = None,
        z_include_missing: bool = True,
        richness_threshold_lower: Optional[float] = None,
        richness_threshold_upper: Optional[float] = None,
        richness_mode: Optional[str] = None,
        richness_include_missing: bool = True,
        flag_quality_zp: Optional[List[int]] = None,
        flag_quality_rs: Optional[List[int]] = None,
        idcluster_list: Optional[List[int]] = None,
        ned_specz_filter: bool = False,
        show_unmerged_clusters: bool = False,
        matching_clusters: bool = False,
        show_cltile_info: bool = True,
        view_bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> List:
        """Build only the filter-dependent traces: merged clusters (+ near-CATRED variants),
        matched-pair ovals and unmerged clusters.

        Used by create_traces for full renders and directly by the incremental
        "Apply filters" path, which replaces just these traces in the figure.
        """
        datamod_detcluster_mergedcat = self._prefilter_merged(
            data,
            z_threshold_lower=z_threshold_lower,
            z_threshold_upper=z_threshold_upper,
            z_include_missing=z_include_missing,
            richness_threshold_lower=richness_threshold_lower,
            richness_threshold_upper=richness_threshold_upper,
            richness_mode=richness_mode,
            richness_include_missing=richness_include_missing,
            flag_quality_zp=flag_quality_zp,
            flag_quality_rs=flag_quality_rs,
            idcluster_list=idcluster_list,
            ned_specz_filter=ned_specz_filter,
        )

        # Viewport culling: only clusters in (or near) the visible window are sent.
        # - More than density_threshold clusters in the visible area: a density grid.
        # - Otherwise markers, with the widest margin around the view (CULL_MARGINS) that
        #   keeps the count within max_points_sent (no margin if none fits).
        # The margin used and whether the result is a density grid travel to the browser
        # in each trace's `meta`; the viewport tracker in ui_callbacks uses them to decide
        # when the next request is needed.
        budget = self.max_points_sent()
        cull_margin = None
        if view_bounds is not None:
            full = datamod_detcluster_mergedcat
            # Count with masks; copy rows only once, for the margin chosen
            view_count = int(self._cull_mask(full, view_bounds, 0.0).sum())
            show_density = view_count > self.density_threshold()
            if show_density:
                cull_margin = self.VIEW_MARGIN  # the grid has a fixed size, so cover the margin
                keep = self._cull_mask(full, view_bounds, cull_margin)
            else:
                for cull_margin in self.CULL_MARGINS:
                    keep = self._cull_mask(full, view_bounds, cull_margin)
                    if int(keep.sum()) <= budget:
                        break
            datamod_detcluster_mergedcat = full[keep]
        else:
            view_count = len(datamod_detcluster_mergedcat)
            show_density = view_count > self.density_threshold()

        self.last_cull = {
            "density": bool(show_density),
            "margin": cull_margin,
            "clusters": int(len(datamod_detcluster_mergedcat)),
        }
        cluster_traces: List = []
        if show_density:
            bounds = view_bounds or (
                float(np.nanmin(datamod_detcluster_mergedcat["RIGHT_ASCENSION_CLUSTER"])),
                float(np.nanmax(datamod_detcluster_mergedcat["RIGHT_ASCENSION_CLUSTER"])),
                float(np.nanmin(datamod_detcluster_mergedcat["DECLINATION_CLUSTER"])),
                float(np.nanmax(datamod_detcluster_mergedcat["DECLINATION_CLUSTER"])),
            )
            density = self._density_trace(datamod_detcluster_mergedcat, bounds)
            # view_count / density_threshold let the browser estimate when a zoom-in
            # brings the view under the threshold, i.e. when to ask for markers
            density.update(meta={
                "cull_margin": cull_margin,
                "density": True,
                "view_count": view_count,
                "density_threshold": self.density_threshold(),
            })
            cluster_traces.append(density)
            return cluster_traces

        self._active_rows = self._row_cache_for(data)
        try:
            _t = time.perf_counter()
            self._add_merged_cluster_trace(
                cluster_traces,
                datamod_detcluster_mergedcat,
                data["algorithm"],
                matching_clusters,
                data_detcluster_by_cltile=data["data_detcluster_by_cltile"],
                snr_threshold_lower_pzwav=snr_threshold_lower_pzwav,
                snr_threshold_upper_pzwav=snr_threshold_upper_pzwav,
                snr_threshold_lower_amico=snr_threshold_lower_amico,
                snr_threshold_upper_amico=snr_threshold_upper_amico,
                snr_include_missing_pzwav=snr_include_missing_pzwav,
                snr_include_missing_amico=snr_include_missing_amico,
                catred_points=catred_points,
                relayout_data=relayout_data,
                show_cltile_info=show_cltile_info,
            )
            self._profiler.record("create_traces:merged_cluster_trace", time.perf_counter() - _t)
        finally:
            self._active_rows = None

        if show_unmerged_clusters:
            _t = time.perf_counter()
            self._add_unmerged_cluster_traces(
                cluster_traces,
                data,
                datamod_detcluster_mergedcat,
                snr_threshold_lower_pzwav,
                snr_threshold_upper_pzwav,
                snr_threshold_lower_amico,
                snr_threshold_upper_amico,
                z_threshold_lower,
                z_threshold_upper,
                catred_points,
                snr_include_missing_pzwav=snr_include_missing_pzwav,
                snr_include_missing_amico=snr_include_missing_amico,
                z_include_missing=z_include_missing,
            )
            self._profiler.record("create_traces:unmerged_traces", time.perf_counter() - _t)

        for trace in cluster_traces:
            trace.update(meta={"cull_margin": cull_margin, "density": False})
        return cluster_traces

    def _prefilter_merged(
        self,
        data: Dict[str, Any],
        z_threshold_lower: Optional[float] = None,
        z_threshold_upper: Optional[float] = None,
        z_include_missing: bool = True,
        richness_threshold_lower: Optional[float] = None,
        richness_threshold_upper: Optional[float] = None,
        richness_mode: Optional[str] = None,
        richness_include_missing: bool = True,
        flag_quality_zp: Optional[List[int]] = None,
        flag_quality_rs: Optional[List[int]] = None,
        idcluster_list: Optional[List[int]] = None,
        ned_specz_filter: bool = False,
    ) -> np.ndarray:
        """Merged catalog after the algorithm-independent filters (redshift, richness,
        uploaded ID list, NED spec-z verification). SNR thresholds differ per algorithm
        and are applied later."""
        merged = self._apply_redshift_filtering(
            data["data_detcluster_mergedcat"], z_threshold_lower, z_threshold_upper, z_include_missing
        )
        merged = self._apply_richness_filtering(
            merged,
            richness_threshold_lower,
            richness_threshold_upper,
            richness_mode,
            flag_quality_zp=flag_quality_zp,
            flag_quality_rs=flag_quality_rs,
            include_missing=richness_include_missing,
        )
        try:
            assert data["paths"]["use_gluematchcat"] == True and idcluster_list is not None
            merged = self._apply_idcluster_filtering(merged, idcluster_list)
        except:
            print(
                "Debug: ID-cluster based filtering skipped - either not using gluematchcat or idcluster_list is None"
            )
        return self._apply_ned_specz_filtering(merged, ned_specz_filter)

    def selected_clusters(
        self,
        data: Dict[str, Any],
        snr_threshold_lower_pzwav: Optional[float] = None,
        snr_threshold_upper_pzwav: Optional[float] = None,
        snr_threshold_lower_amico: Optional[float] = None,
        snr_threshold_upper_amico: Optional[float] = None,
        snr_include_missing_pzwav: bool = True,
        snr_include_missing_amico: bool = True,
        matching_clusters: bool = False,
        **prefilter_kw,
    ) -> np.ndarray:
        """Merged clusters passing all filters, whole sky (no culling): the rows the
        sky map would show as markers. Used by the globe overview's density."""
        merged = self._prefilter_merged(data, **prefilter_kw)
        algorithm = str(data.get("algorithm", "")).lower()
        names = merged.dtype.names or ()
        snr = {
            "pzwav": (snr_threshold_lower_pzwav, snr_threshold_upper_pzwav, snr_include_missing_pzwav),
            "amico": (snr_threshold_lower_amico, snr_threshold_upper_amico, snr_include_missing_amico),
        }
        if "DET_CODE_NB" in names and algorithm == "both":
            parts = []
            for det_code, alg in ((2, "pzwav"), (1, "amico")):
                part = self._apply_snr_filtering(merged[merged["DET_CODE_NB"] == det_code], *snr[alg])
                if matching_clusters and "CROSS_ID_CLUSTER" in names:
                    part = part[~np.isnan(part["CROSS_ID_CLUSTER"])]
                parts.append(part)
            return np.concatenate(parts)
        if algorithm in snr:
            return self._apply_snr_filtering(merged, *snr[algorithm])
        return merged

    def tile_ids_for_rows(self, data: Dict[str, Any], subset: np.ndarray) -> List[str]:
        """CL tile ID of each row of ``subset`` ("?" when unknown), via the per-row cache."""
        by_cltile = data.get("data_detcluster_by_cltile")
        if not by_cltile or len(subset) == 0:
            return ["?"] * len(subset)
        self._active_rows = self._row_cache_for(data)
        try:
            return self._tile_colors_for(subset, by_cltile)[1]
        finally:
            self._active_rows = None

    def row_column(self, data: Dict[str, Any], subset: np.ndarray, key: str, build) -> np.ndarray:
        """Per-row values of ``subset`` for a derived column ``key``.

        ``build(rows)`` computes the column for any rows; on first use it runs over the
        whole catalog and is kept in the row cache, later calls only slice it.
        """
        cache = self._row_cache_for(data)
        if cache is not None:
            self._active_rows = cache
            try:
                pos = self._row_positions(subset)
            finally:
                self._active_rows = None
            if pos is not None:
                if cache.get(key) is None:
                    _t = time.perf_counter()
                    cache[key] = build(cache["merged"])
                    self._profiler.record(f"row_cache:{key}", time.perf_counter() - _t)
                return cache[key][pos]
        return build(subset)

    # ------------------------------------------------------------------
    # Per-row cache: tile colours and richness strings are row-independent,
    # so compute them once per loaded catalog and slice by cluster ID.
    # ------------------------------------------------------------------

    def _row_cache_for(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return (building on first use) the per-row cache stored in the data dict.

        Stored in ``data`` so it lives as long as the DataLoader's cached catalog,
        and is inherited by forked background renders. Returns None (callers fall
        back to direct computation) when cluster IDs are missing or not unique.
        """
        merged = data.get("data_detcluster_mergedcat")
        by_cltile = data.get("data_detcluster_by_cltile")
        if merged is None or len(merged) == 0 or "ID_UNIQUE_CLUSTER" not in (merged.dtype.names or ()):
            return None

        cache = data.get("_render_row_cache")
        if cache is not None and cache["merged"] is merged and cache["by_cltile"] is by_cltile:
            return cache

        _t = time.perf_counter()
        ids = np.asarray(merged["ID_UNIQUE_CLUSTER"])
        order = np.argsort(ids, kind="stable")
        sorted_ids = ids[order]
        if len(sorted_ids) > 1 and np.any(sorted_ids[1:] == sorted_ids[:-1]):
            print("Debug: ID_UNIQUE_CLUSTER not unique - per-row render cache disabled")
            data["_render_row_cache"] = None
            return None

        cache = {
            "merged": merged,
            "by_cltile": by_cltile,
            "order": order,
            "sorted_ids": sorted_ids,
            "colors": None,  # built lazily: only needed when CL-tile info is shown
            "tile_ids": None,
        }
        data["_render_row_cache"] = cache
        self._profiler.record("row_cache:build", time.perf_counter() - _t)
        return cache

    def _row_positions(self, subset: np.ndarray) -> Optional[np.ndarray]:
        """Positions of ``subset`` rows in the cached full catalog, or None if not resolvable."""
        cache = self._active_rows
        if cache is None or len(subset) == 0:
            return None
        if "ID_UNIQUE_CLUSTER" not in (subset.dtype.names or ()):
            return None
        ids = np.asarray(subset["ID_UNIQUE_CLUSTER"])
        sorted_ids = cache["sorted_ids"]
        idx = np.searchsorted(sorted_ids, ids)
        if np.any(idx >= len(sorted_ids)) or np.any(sorted_ids[np.minimum(idx, len(sorted_ids) - 1)] != ids):
            return None
        return cache["order"][idx]

    def _tile_colors_for(
        self, subset: np.ndarray, data_detcluster_by_cltile: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """Cached equivalent of _compute_merged_tile_colors(subset, ...)."""
        cache = self._active_rows
        pos = self._row_positions(subset)
        if pos is None or cache["by_cltile"] is not data_detcluster_by_cltile:
            return self._compute_merged_tile_colors(subset, data_detcluster_by_cltile)
        if cache["colors"] is None:
            colors, tile_ids = self._compute_merged_tile_colors(cache["merged"], data_detcluster_by_cltile)
            cache["colors"] = np.asarray(colors, dtype=object)
            cache["tile_ids"] = np.asarray(tile_ids, dtype=object)
        return cache["colors"][pos].tolist(), cache["tile_ids"][pos].tolist()

    def _richness_for(self, subset: np.ndarray) -> "tuple[list, list, list, list]":
        """Cached equivalent of _richness_arrays(subset)."""
        pos = self._row_positions(subset)
        if pos is None:
            return self._richness_arrays(subset)
        return tuple(col[pos].tolist() for col in self._active_rows["richness"])

    def _get_catred_data_points(
        self,
        manual_catred_data: Optional[Dict],
        existing_catred_traces: Optional[List],
        catred_box_data: Optional[Dict],
    ) -> Optional[List]:
        """Get all CATRED data points for proximity-based enhancement."""
        all_points = []

        # Clear bounds cache when getting new CATRED data (important for multiple renders)
        self.proximity_detector.clear_bounds_cache()

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
                # In background callbacks, in-memory current_catred_data can be empty even
                # when traces are present in the figure. Recover proximity points directly
                # from preserved CATRED traces to keep near-CATRED highlighting/clickability.
                recovered_points = 0
                for trace in existing_catred_traces:
                    xs = None
                    ys = None
                    if isinstance(trace, dict):
                        xs = trace.get("x", [])
                        ys = trace.get("y", [])
                    else:
                        xs = getattr(trace, "x", [])
                        ys = getattr(trace, "y", [])

                    if xs is None or ys is None:
                        continue

                    for ra, dec in zip(xs, ys):
                        if ra is None or dec is None:
                            continue
                        all_points.append((float(ra), float(dec)))
                        recovered_points += 1

                if recovered_points > 0:
                    print(
                        f"Debug: Recovered {recovered_points} CATRED points from existing traces"
                    )
        else:
            # No existing CATRED traces - clear stored CATRED data to revert markers
            if hasattr(self, "current_catred_data"):
                self.current_catred_data = None
                print("Debug: CATRED data cleared - reverting marker enhancements")
            # Clear bounds cache as well
            self.proximity_detector.clear_bounds_cache()

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

        self.proximity_detector.clear()

    def _apply_snr_filtering(
        self,
        cluster_data: np.ndarray,
        snr_lower: Optional[float],
        snr_upper: Optional[float],
        include_missing: bool = True,
    ) -> np.ndarray:
        """Apply SNR filtering to merged cluster data."""
        if snr_lower is None and snr_upper is None:
            return cluster_data

        col = cluster_data["SNR_CLUSTER"]
        if snr_lower is not None and snr_upper is not None:
            range_mask = (col >= snr_lower) & (col <= snr_upper)
        elif snr_upper is not None:
            range_mask = col <= snr_upper
        else:
            range_mask = col >= snr_lower

        if include_missing:
            range_mask = range_mask | np.isnan(col)

        return cluster_data[range_mask]

    def _apply_redshift_filtering(
        self,
        cluster_data: np.ndarray,
        z_threshold_lower: Optional[float],
        z_threshold_upper: Optional[float],
        include_missing: bool = True,
    ) -> np.ndarray:
        """Apply redshift filtering to merged cluster data."""
        if z_threshold_lower is None and z_threshold_upper is None:
            return cluster_data

        col = cluster_data["Z_CLUSTER"]
        if z_threshold_lower is not None and z_threshold_upper is not None:
            range_mask = (col >= z_threshold_lower) & (col <= z_threshold_upper)
        elif z_threshold_upper is not None:
            range_mask = col <= z_threshold_upper
        else:
            range_mask = col >= z_threshold_lower

        if include_missing:
            range_mask = range_mask | np.isnan(col)

        return cluster_data[range_mask]

    def _apply_richness_filtering(
        self,
        cluster_data: np.ndarray,
        richness_lower: Optional[float],
        richness_upper: Optional[float],
        richness_mode: Optional[str],
        flag_quality_zp: Optional[List[int]] = None,
        flag_quality_rs: Optional[List[int]] = None,
        include_missing: bool = True,
    ) -> np.ndarray:
        """Apply richness filtering using RICHNESS_ZP/RS range and FLAG_QUALITY_ZP/RS checklist."""
        if richness_mode is None or richness_mode == "none":
            return cluster_data

        col = "RICHNESS_ZP" if richness_mode == "zp" else "RICHNESS_RS"
        flag_col = "FLAG_QUALITY_ZP" if richness_mode == "zp" else "FLAG_QUALITY_RS"
        flag_values = flag_quality_zp if richness_mode == "zp" else flag_quality_rs

        if col not in cluster_data.dtype.names:
            print(f"Debug: {col} column not found, skipping richness filtering")
            return cluster_data

        if richness_lower is not None or richness_upper is not None:
            col_data = cluster_data[col]
            if richness_lower is not None and richness_upper is not None:
                range_mask = (col_data >= richness_lower) & (col_data <= richness_upper)
            elif richness_upper is not None:
                range_mask = col_data <= richness_upper
            else:
                range_mask = col_data >= richness_lower

            if include_missing:
                range_mask = range_mask | np.isnan(col_data)

            cluster_data = cluster_data[range_mask]

        if flag_values is not None and flag_col in cluster_data.dtype.names:
            cluster_data = cluster_data[np.isin(cluster_data[flag_col], flag_values)]

        return cluster_data

    @staticmethod
    def _richness_arrays(arr: np.ndarray) -> "tuple[list, list, list, list]":
        """Return (richness_zp_str, flag_zp_str, richness_rs_str, flag_rs_str) pre-formatted string arrays.

        Uses "N/A" when column absent so Plotly renders cleanly without format specifiers.
        """
        n = len(arr)
        names = arr.dtype.names or []

        def _fmt_float(a, col):
            if col not in names:
                return ["N/A"] * n
            return [f"{v:.2f}" if not (v != v) else "N/A" for v in a[col]]  # v != v → isnan

        def _fmt_int(a, col):
            if col not in names:
                return ["N/A"] * n
            return [str(int(v)) for v in a[col]]

        return (
            _fmt_float(arr, "RICHNESS_ZP"),
            _fmt_int(arr, "FLAG_QUALITY_ZP"),
            _fmt_float(arr, "RICHNESS_RS"),
            _fmt_int(arr, "FLAG_QUALITY_RS"),
        )

    def _filter_detfits_by_unique_ids(
        self,
        cluster_data: np.ndarray,
        merged_selected: np.ndarray,
        angular_tolerance: float = 2.0,
        z_tolerance: float = 0.02,
    ) -> StructuredArray:
        """Filter per-tile cluster data by RA/Dec + Z proximity to merged selected clusters."""
        if merged_selected is None or len(merged_selected) == 0 or len(cluster_data) == 0:
            return cluster_data
        try:
            tol_deg = angular_tolerance / 3600.0
            m_ra  = np.asarray(merged_selected["RIGHT_ASCENSION_CLUSTER"], dtype=float)
            m_dec = np.asarray(merged_selected["DECLINATION_CLUSTER"],     dtype=float)
            m_z   = np.asarray(merged_selected["Z_CLUSTER"],               dtype=float)
            t_ra  = np.asarray(cluster_data["RIGHT_ASCENSION_CLUSTER"],    dtype=float)
            t_dec = np.asarray(cluster_data["DECLINATION_CLUSTER"],        dtype=float)
            t_z   = np.asarray(cluster_data["Z_CLUSTER"],                  dtype=float)
            d2     = (t_ra[:, None] - m_ra[None, :]) ** 2 + (t_dec[:, None] - m_dec[None, :]) ** 2
            ang_ok = np.sqrt(d2) <= tol_deg
            z_ok   = np.abs(t_z[:, None] - m_z[None, :]) <= z_tolerance
            keep   = np.any(ang_ok & z_ok, axis=1)
            return cast(StructuredArray, cluster_data[keep])
        except Exception as e:
            print(f"Debug: _filter_detfits_by_unique_ids failed: {e}")
            return cluster_data

    def _apply_idcluster_filtering(
            self,
            cluster_data: np.ndarray,
            idcluster_list: Optional[Union[List[int], np.ndarray]],
    ) -> np.ndarray:
        """Apply IDCLUSTER filtering to merged cluster data."""
        if idcluster_list is None:
            return cluster_data
        
        try:
            mask = np.isin(cluster_data['ID_UNIQUE_CLUSTER'], idcluster_list)
            filtered_data = cluster_data[mask]
        except Exception as e:
            print(f"Error applying IDCLUSTER filtering: {e}")
            print(f"IDCLUSTER list provided: {idcluster_list}")
            return cluster_data

        return filtered_data

    def _apply_ned_specz_filtering(
        self,
        cluster_data: np.ndarray,
        filter_active: bool,
    ) -> np.ndarray:
        """Restrict cluster points to those with a NED spec-z cross-match.

        No-op (returns cluster_data unchanged) if the switch is off or no
        NED catalog is configured/loaded.
        """
        if not filter_active or self.ned_handler is None or not self.ned_handler.is_available():
            return cluster_data

        try:
            mask = np.isin(cluster_data["ID_UNIQUE_CLUSTER"], self.ned_handler.get_unique_cluster_ids())
            return cluster_data[mask]
        except Exception as e:
            print(f"Error applying NED spec-z filtering: {e}")
            return cluster_data

    def _check_zoom_threshold(self, relayout_data: Optional[Dict], show_mer_tiles: bool) -> bool:
        """Check if zoom level meets threshold for CATRED data display (< 2 degrees)."""
        if not relayout_data:
            print(
                f"Debug: Zoom check skipped - no relayout_data available"
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
        if not manual_catred_data:
            if zoom_threshold_met:
                print(
                    f"Debug: CATRED scatter conditions met but no manual data provided - use render button"
                )
            else:
                print(
                    f"Debug: CATRED scatter data conditions not met - "
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

        # catred_handler.current_catred_data is intentionally NOT overwritten here.
        # It holds the viewport-clipped flat dict set by _clip_to_viewport() in the
        # load path, which is the format expected by aladin_callbacks for Aladin push.

        # NOTE: diskcache persistence moved to create_traces() so both tile
        # and box traces are captured in a single write after both methods run.
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
        if not catred_box_data:
            print(
                f"Debug: CATRED box trace skipped - no catred_box_data provided"
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

    MAX_OVALS = 20000  # one trace for all ovals, so the cap is about points, not traces

    def _matched_pair_trace(self, pzwav_data, amico_data, relayout_data, n_points=48):
        """All matched PZWAV↔AMICO pairs in the view as ONE filled Scatter trace.

        Pairs are found with an ID lookup (CROSS_ID_CLUSTER → AMICO ID_UNIQUE_CLUSTER)
        and each ellipse (centre = pair midpoint, semi-major = half separation + 0.01°,
        semi-minor = half of that, rotated along the pair) is joined with NaN gaps so
        Plotly fills them independently.
        """
        if len(pzwav_data) == 0 or len(amico_data) == 0:
            return None

        # Only clusters with a cross-match ID can be paired
        p = pzwav_data[np.isfinite(np.asarray(pzwav_data["CROSS_ID_CLUSTER"], dtype=float))]
        if relayout_data and "xaxis.range[0]" in relayout_data:
            ra_lo, ra_hi = sorted((relayout_data.get("xaxis.range[0]", 0), relayout_data.get("xaxis.range[1]", 360)))
            dec_lo, dec_hi = sorted((relayout_data.get("yaxis.range[0]", -90), relayout_data.get("yaxis.range[1]", 90)))
            ra, dec = p["RIGHT_ASCENSION_CLUSTER"], p["DECLINATION_CLUSTER"]
            p = p[(ra >= ra_lo) & (ra <= ra_hi) & (dec >= dec_lo) & (dec <= dec_hi)]
        if len(p) == 0:
            return None

        amico_ids = np.asarray(amico_data["ID_UNIQUE_CLUSTER"])
        order = np.argsort(amico_ids, kind="stable")
        sorted_ids = amico_ids[order]
        wanted = np.asarray(p["CROSS_ID_CLUSTER"]).astype(amico_ids.dtype, copy=False)
        idx = np.searchsorted(sorted_ids, wanted)
        idx_clip = np.minimum(idx, len(sorted_ids) - 1)
        found = sorted_ids[idx_clip] == wanted
        if not np.any(found):
            return None
        p = p[found]
        a = amico_data[order[idx_clip[found]]]

        if len(p) > self.MAX_OVALS:
            top = np.argsort(np.asarray(p["SNR_CLUSTER"]))[-self.MAX_OVALS:]
            p, a = p[top], a[top]

        ra1 = np.asarray(p["RIGHT_ASCENSION_CLUSTER"], dtype=float)
        dec1 = np.asarray(p["DECLINATION_CLUSTER"], dtype=float)
        ra2 = np.asarray(a["RIGHT_ASCENSION_CLUSTER"], dtype=float)
        dec2 = np.asarray(a["DECLINATION_CLUSTER"], dtype=float)
        center_ra, center_dec = (ra1 + ra2) / 2, (dec1 + dec2) / 2
        semi_major = np.hypot(ra2 - ra1, dec2 - dec1) / 2 + 0.01
        semi_minor = semi_major * 0.5
        angle = np.where(ra2 != ra1, np.arctan2(dec2 - dec1, ra2 - ra1), np.pi / 2)

        theta = np.linspace(0, 2 * np.pi, n_points)
        ex = semi_major[:, None] * np.cos(theta)[None, :]
        ey = semi_minor[:, None] * np.sin(theta)[None, :]
        cos_a, sin_a = np.cos(angle)[:, None], np.sin(angle)[:, None]
        xs = center_ra[:, None] + ex * cos_a - ey * sin_a
        ys = center_dec[:, None] + ex * sin_a + ey * cos_a
        gap = np.full((len(p), 1), np.nan)
        x = np.hstack([xs, gap]).ravel()
        y = np.hstack([ys, gap]).ravel()

        return go.Scatter(
            x=x,
            y=y,
            mode="lines",
            fill="toself",
            fillcolor="rgba(0, 255, 0, 0.3)",
            line=dict(color="green", width=1, dash="dot"),
            name="Matched Pair",
            showlegend=False,
            hoverinfo="skip",
        )

    @staticmethod
    def _line_colors(colors, width: int = 2) -> Dict[str, Any]:
        """Marker outline colours, one per point, as palette indices plus a discrete
        colorscale. A list of colour strings is validated element by element by Plotly
        (most of the build time for big traces) and sent as text; indices go as one
        byte per point in binary."""
        if isinstance(colors, str):
            return dict(width=width, color=colors)
        names = np.asarray(colors, dtype=object).astype(str)
        if len(names) == 0:
            return dict(width=width, color="gray")
        palette, index = np.unique(names, return_inverse=True)
        if len(palette) == 1:
            return dict(width=width, color=str(palette[0]))
        last = len(palette) - 1
        return dict(
            width=width,
            color=index.astype(np.uint8 if last < 256 else np.float32),
            colorscale=[[i / last, str(c)] for i, c in enumerate(palette)],
            cmin=0,
            cmax=last,
            autocolorscale=False,
        )

    @staticmethod
    def _cluster_customdata(subset, det_codes=None, tile_ids=None):
        """Per-point cluster ID (ID_UNIQUE_CLUSTER) as a 1-D numeric array.

        Viewport patches are limited by transfer through the SSH tunnel, so markers carry
        only the ID: the hover shows ID and RA/Dec, and the cluster click handler resolves
        the merged row by ID for SNR, z and tile. (det_codes / tile_ids are accepted for
        older call sites and ignored.)
        """
        if not len(subset):
            return np.zeros(0, dtype=np.float32)
        ids = np.asarray(subset["ID_UNIQUE_CLUSTER"], dtype=float)
        # float32 halves the payload; it holds integers exactly only below 2**24, so IDs
        # beyond that keep float64
        exact32 = bool(np.all(~np.isfinite(ids) | (np.abs(ids) < 2**24)))
        return ids.astype(np.float32 if exact32 else np.float64)

    @staticmethod
    def _coords32(values):
        """Marker positions as float32: half the bytes of float64, ~0.1 arcsec resolution
        at RA 360° (display only; clicks resolve clusters by ID)."""
        return np.asarray(values, dtype=np.float32)

    @staticmethod
    def tile_id_for(data: Dict[str, Any], cluster_id) -> Optional[str]:
        """CL tile of a merged cluster, from the per-row render cache (None if the tile
        colours were never computed, i.e. CL-tile info has not been shown)."""
        cache = data.get("_render_row_cache") if isinstance(data, dict) else None
        if not cache or cache.get("tile_ids") is None or cluster_id is None:
            return None
        try:
            cid = float(cluster_id)
        except (TypeError, ValueError):
            return None
        sorted_ids = cache["sorted_ids"]
        i = int(np.searchsorted(sorted_ids, cid))
        if i >= len(sorted_ids) or float(sorted_ids[i]) != cid:
            return None
        tile = cache["tile_ids"][cache["order"][i]]
        return None if tile in (None, "?") else str(tile)

    def _add_merged_cluster_trace(
        self,
        data_traces: List,
        datamod_detcluster_mergedcat: np.ndarray,
        algorithm: str,
        matching_clusters: bool,
        data_detcluster_by_cltile: Optional[Dict[str, Any]] = None,
        snr_threshold_lower_pzwav: Optional[float] = None,
        snr_threshold_upper_pzwav: Optional[float] = None,
        snr_threshold_lower_amico: Optional[float] = None,
        snr_threshold_upper_amico: Optional[float] = None,
        snr_include_missing_pzwav: bool = True,
        snr_include_missing_amico: bool = True,
        catred_points: Optional[List] = None,
        relayout_data: Optional[Dict] = None,
        show_cltile_info: bool = True,
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
                    pzwav_data,
                    snr_threshold_lower_pzwav,
                    snr_threshold_upper_pzwav,
                    snr_include_missing_pzwav,
                )
                amico_data = self._apply_snr_filtering(
                    amico_data,
                    snr_threshold_lower_amico,
                    snr_threshold_upper_amico,
                    snr_include_missing_amico,
                )

                if matching_clusters:  # has_det_code & algorithm=BOTH
                    pzwav_data = pzwav_data[np.logical_not(np.isnan(pzwav_data["CROSS_ID_CLUSTER"]))]
                    amico_data = amico_data[np.logical_not(np.isnan(amico_data["CROSS_ID_CLUSTER"]))]
                    oval_trace = self._matched_pair_trace(pzwav_data, amico_data, relayout_data)
                    if oval_trace is not None:
                        data_traces.append(oval_trace)

                # PZWAV trace - has_det_code & algorithm=BOTH 
                if len(pzwav_data) > 0:
                    pzwav_colors, pzwav_tile_ids = (
                        self._tile_colors_for(pzwav_data, data_detcluster_by_cltile)
                        if (show_cltile_info and data_detcluster_by_cltile)
                        else (["royalblue"] * len(pzwav_data), ["?"] * len(pzwav_data))
                    )
                    pzwav_trace = go.Scattergl(
                        x=self._coords32(pzwav_data["RIGHT_ASCENSION_CLUSTER"]),
                        y=self._coords32(pzwav_data["DECLINATION_CLUSTER"]),
                        mode="markers",
                        marker=dict(
                            size=10, symbol="x-thin", line=self._line_colors(pzwav_colors)
                        ),
                        name=f"Merged PZWAV",
                        legendgroup="merged_pzwav",
                        showlegend=True,
                        customdata=self._cluster_customdata(pzwav_data, pzwav_data["DET_CODE_NB"], pzwav_tile_ids),
                        hovertemplate=(
                            "<b>Cluster (PZWAV)</b><br>"
                            + "ID: %{customdata:d}<br>"
                            + "<span style='color:red'>RA: %{x:.2f}°</span><br>"
                            + "<span style='color:red'>Dec: %{y:.2f}°</span><br>"
                            + "<extra></extra>"
                        ),
                        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                    )
                    data_traces.append(pzwav_trace)

                # AMICO trace - has_det_code & algorithm=BOTH
                if len(amico_data) > 0:
                    amico_colors, amico_tile_ids = (
                        self._tile_colors_for(amico_data, data_detcluster_by_cltile)
                        if (show_cltile_info and data_detcluster_by_cltile)
                        else (["tomato"] * len(amico_data), ["?"] * len(amico_data))
                    )
                    amico_trace = go.Scattergl(
                        x=self._coords32(amico_data["RIGHT_ASCENSION_CLUSTER"]),
                        y=self._coords32(amico_data["DECLINATION_CLUSTER"]),
                        mode="markers",
                        marker=dict(
                            size=10, symbol="cross-thin", line=self._line_colors(amico_colors)
                        ),
                        name=f"Merged AMICO",
                        legendgroup="merged_amico",
                        showlegend=True,
                        customdata=self._cluster_customdata(amico_data, amico_data["DET_CODE_NB"], amico_tile_ids),
                        hovertemplate=(
                            "<b>Cluster (AMICO)</b><br>"
                            + "ID: %{customdata:d}<br>"
                            + "<span style='color:red'>RA: %{x:.2f}°</span><br>"
                            + "<span style='color:red'>Dec: %{y:.2f}°</span><br>"
                            + "<extra></extra>"
                        ),
                        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                    )
                    data_traces.append(amico_trace)
            else:
                # Single algorithm or no DET_CODE_NB column
                symbol = "cross-thin" if algorithm.lower() == "amico" else "x-thin"

                if algorithm.lower() == "pzwav":
                    datamod_detcluster_mergedcat = self._apply_snr_filtering(
                        datamod_detcluster_mergedcat,
                        snr_threshold_lower_pzwav,
                        snr_threshold_upper_pzwav,
                        snr_include_missing_pzwav,
                    )
                elif algorithm.lower() == "amico":
                    datamod_detcluster_mergedcat = self._apply_snr_filtering(
                        datamod_detcluster_mergedcat,
                        snr_threshold_lower_amico,
                        snr_threshold_upper_amico,
                        snr_include_missing_amico,
                    )

                if has_det_code:
                    det_code_values_customdata = datamod_detcluster_mergedcat["DET_CODE_NB"]
                else:
                    det_code_values_customdata = np.full(
                        len(datamod_detcluster_mergedcat), 2 if algorithm.lower() == "pzwav" else 1
                    )

                merged_colors, merged_tile_ids = (
                    self._tile_colors_for(
                        datamod_detcluster_mergedcat, data_detcluster_by_cltile
                    )
                    if (show_cltile_info and data_detcluster_by_cltile)
                    else (["royalblue" if algorithm.lower() == "pzwav" else "tomato"] * len(datamod_detcluster_mergedcat), ["?"] * len(datamod_detcluster_mergedcat))
                )
                merged_trace = go.Scattergl(
                    x=self._coords32(datamod_detcluster_mergedcat["RIGHT_ASCENSION_CLUSTER"]),
                    y=self._coords32(datamod_detcluster_mergedcat["DECLINATION_CLUSTER"]),
                    mode="markers",
                    marker=dict(size=10, symbol=symbol, line=self._line_colors(merged_colors)),
                    name=f"Merged {algorithm}",
                    customdata=self._cluster_customdata(datamod_detcluster_mergedcat, det_code_values_customdata, merged_tile_ids),
                    hovertemplate=(
                        f"<b>Cluster ({algorithm})</b><br>"
                        + "ID: %{customdata:d}<br>"
                        + "<span style='color:red'>RA: %{x:.2f}°</span><br>"
                        + "<span style='color:red'>Dec: %{y:.2f}°</span><br>"
                        + "<extra></extra>"
                    ),
                    hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                )
                data_traces.append(merged_trace)
        else:
            # CATRED data present - create separate traces based on proximity to CATRED points
            near_catred_mask = self.proximity_detector.check_proximity_batch(
                datamod_detcluster_mergedcat["RIGHT_ASCENSION_CLUSTER"],
                datamod_detcluster_mergedcat["DECLINATION_CLUSTER"],
                catred_points,
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
                        pzwav_away,
                        snr_threshold_lower_pzwav,
                        snr_threshold_upper_pzwav,
                        snr_include_missing_pzwav,
                    )
                    amico_away = self._apply_snr_filtering(
                        amico_away,
                        snr_threshold_lower_amico,
                        snr_threshold_upper_amico,
                        snr_include_missing_amico,
                    )

                    # PZWAV away trace
                    if len(pzwav_away) > 0:
                        pzwav_away_colors, pzwav_away_tile_ids = (
                            self._tile_colors_for(
                                pzwav_away, data_detcluster_by_cltile
                            )
                            if (show_cltile_info and data_detcluster_by_cltile)
                            else (["royalblue"] * len(pzwav_away), ["?"] * len(pzwav_away))
                        )
                        normal_trace_pzwav = go.Scattergl(
                            x=self._coords32(pzwav_away["RIGHT_ASCENSION_CLUSTER"]),
                            y=self._coords32(pzwav_away["DECLINATION_CLUSTER"]),
                            mode="markers",
                            marker=dict(
                                size=10, symbol="x-thin", line=self._line_colors(pzwav_away_colors)
                            ),
                            name=f"PZWAV (Merged)",  # - {len(pzwav_away)} clusters',
                            legendgroup="merged_pzwav",
                            showlegend=True,
                            customdata=self._cluster_customdata(pzwav_away, pzwav_away["DET_CODE_NB"], pzwav_away_tile_ids),
                            hovertemplate=(
                                "<b>Cluster (PZWAV)</b><br>"
                                + "ID: %{customdata:d}<br>"
                                + "<span style='color:red'>RA: %{x:.2f}°</span><br>"
                                + "<span style='color:red'>Dec: %{y:.2f}°</span><br>"
                                + "<extra></extra>"
                            ),
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                        )
                        data_traces.append(normal_trace_pzwav)

                    # AMICO away trace
                    if len(amico_away) > 0:
                        amico_away_colors, amico_away_tile_ids = (
                            self._tile_colors_for(
                                amico_away, data_detcluster_by_cltile
                            )
                            if (show_cltile_info and data_detcluster_by_cltile)
                            else (["tomato"] * len(amico_away), ["?"] * len(amico_away))
                        )
                        normal_trace_amico = go.Scattergl(
                            x=self._coords32(amico_away["RIGHT_ASCENSION_CLUSTER"]),
                            y=self._coords32(amico_away["DECLINATION_CLUSTER"]),
                            mode="markers",
                            marker=dict(
                                size=10, symbol="cross-thin", line=self._line_colors(amico_away_colors)
                            ),
                            name=f"AMICO (Merged)",  # - {len(amico_away)} clusters',
                            legendgroup="merged_amico",
                            showlegend=True,
                            customdata=self._cluster_customdata(amico_away, amico_away["DET_CODE_NB"], amico_away_tile_ids),
                            hovertemplate=(
                                "<b>Cluster (AMICO)</b><br>"
                                + "ID: %{customdata:d}<br>"
                                + "<span style='color:red'>RA: %{x:.2f}°</span><br>"
                                + "<span style='color:red'>Dec: %{y:.2f}°</span><br>"
                                + "<extra></extra>"
                            ),
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                        )
                        data_traces.append(normal_trace_amico)
                else:
                    # Single algorithm
                    symbol = "cross-thin" if algorithm == "AMICO" else "x-thin"

                    if algorithm.lower() == "pzwav":
                        away_from_catred_data = self._apply_snr_filtering(
                            away_from_catred_data,
                            snr_threshold_lower_pzwav,
                            snr_threshold_upper_pzwav,
                            snr_include_missing_pzwav,
                        )
                    elif algorithm.lower() == "amico":
                        away_from_catred_data = self._apply_snr_filtering(
                            away_from_catred_data,
                            snr_threshold_lower_amico,
                            snr_threshold_upper_amico,
                            snr_include_missing_amico,
                        )

                    if has_det_code:
                        det_code_values_customdata = away_from_catred_data["DET_CODE_NB"]
                    else:
                        det_code_values_customdata = np.full(
                            len(away_from_catred_data), 2 if algorithm.lower() == "pzwav" else 1
                        )

                    away_colors, away_tile_ids = (
                        self._tile_colors_for(
                            away_from_catred_data, data_detcluster_by_cltile
                        )
                        if (show_cltile_info and data_detcluster_by_cltile)
                        else (["royalblue" if algorithm.lower() == "pzwav" else "tomato"] * len(away_from_catred_data), ["?"] * len(away_from_catred_data))
                    )
                    normal_trace = go.Scattergl(
                        x=self._coords32(away_from_catred_data["RIGHT_ASCENSION_CLUSTER"]),
                        y=self._coords32(away_from_catred_data["DECLINATION_CLUSTER"]),
                        mode="markers",
                        marker=dict(size=10, symbol=symbol, line=self._line_colors(away_colors)),
                        name=f"{algorithm} (Merged)",
                        legendgroup=f"merged_{algorithm.lower()}",
                        showlegend=True,
                        customdata=self._cluster_customdata(away_from_catred_data, det_code_values_customdata, away_tile_ids),
                        hovertemplate=(
                            f"<b>Cluster ({algorithm})</b><br>"
                            + "ID: %{customdata:d}<br>"
                            + "<span style='color:red'>RA: %{x:.2f}°</span><br>"
                            + "<span style='color:red'>Dec: %{y:.2f}°</span><br>"
                            + "<extra></extra>"
                        ),
                        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
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
                        pzwav_near,
                        snr_threshold_lower_pzwav,
                        snr_threshold_upper_pzwav,
                        snr_include_missing_pzwav,
                    )
                    amico_near = self._apply_snr_filtering(
                        amico_near,
                        snr_threshold_lower_amico,
                        snr_threshold_upper_amico,
                        snr_include_missing_amico,
                    )

                    # PZWAV enhanced traces
                    if len(pzwav_near) > 0:
                        pzwav_near_colors, pzwav_near_tile_ids = (
                            self._tile_colors_for(
                                pzwav_near, data_detcluster_by_cltile
                            )
                            if (show_cltile_info and data_detcluster_by_cltile)
                            else (["royalblue"] * len(pzwav_near), ["?"] * len(pzwav_near))
                        )
                        _pzwav_near_customdata = self._cluster_customdata(pzwav_near, pzwav_near["DET_CODE_NB"], pzwav_near_tile_ids)
                        _pzwav_near_hovertemplate = (
                            "<b>Cluster (PZWAV)</b><br>"
                            + "ID: %{customdata:d}<br>"
                            + "<span style='color:red'>RA: %{x:.2f}°</span><br>"
                            + "<span style='color:red'>Dec: %{y:.2f}°</span><br>"
                            + "<extra></extra>"
                        )
                        glow_trace_pzwav = create_glow_trace(
                            pzwav_near["RIGHT_ASCENSION_CLUSTER"],
                            pzwav_near["DECLINATION_CLUSTER"],
                            size=28,
                            shape="circle",
                            showlegend=False,
                            name="Merged PZWAV (in CATRED region)",
                        )
                        glow_trace_pzwav["legendgroup"] = "merged_pzwav"
                        glow_trace_pzwav.update(
                            customdata=_pzwav_near_customdata,
                            hovertemplate=_pzwav_near_hovertemplate,
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                            hoverinfo="all",
                        )
                        data_traces.append(glow_trace_pzwav)

                        enhanced_trace_pzwav = go.Scattergl(
                            x=self._coords32(pzwav_near["RIGHT_ASCENSION_CLUSTER"]),
                            y=self._coords32(pzwav_near["DECLINATION_CLUSTER"]),
                            mode="markers",
                            marker=dict(
                                size=10,
                                symbol="x-thin",
                                line=self._line_colors(pzwav_near_colors),
                                opacity=1.0,
                            ),
                            name=f"PZWAV (Merged, near CATRED) - {len(pzwav_near)} clusters",
                            legendgroup="merged_pzwav",
                            showlegend=False,
                            customdata=_pzwav_near_customdata,
                            hovertemplate=_pzwav_near_hovertemplate,
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                        )
                        data_traces.append(enhanced_trace_pzwav)

                    # AMICO enhanced traces
                    if len(amico_near) > 0:
                        amico_near_colors, amico_near_tile_ids = (
                            self._tile_colors_for(
                                amico_near, data_detcluster_by_cltile
                            )
                            if (show_cltile_info and data_detcluster_by_cltile)
                            else (["tomato"] * len(amico_near), ["?"] * len(amico_near))
                        )
                        _amico_near_customdata = self._cluster_customdata(amico_near, amico_near["DET_CODE_NB"], amico_near_tile_ids)
                        _amico_near_hovertemplate = (
                            "<b>Cluster (AMICO)</b><br>"
                            + "ID: %{customdata:d}<br>"
                            + "<span style='color:red'>RA: %{x:.2f}°</span><br>"
                            + "<span style='color:red'>Dec: %{y:.2f}°</span><br>"
                            + "<extra></extra>"
                        )
                        glow_trace_amico = create_glow_trace(
                            amico_near["RIGHT_ASCENSION_CLUSTER"],
                            amico_near["DECLINATION_CLUSTER"],
                            size=28,
                            shape="circle",
                            showlegend=False,
                            name="Merged AMICO (in CATRED region)",
                        )
                        glow_trace_amico["legendgroup"] = "merged_amico"
                        glow_trace_amico.update(
                            customdata=_amico_near_customdata,
                            hovertemplate=_amico_near_hovertemplate,
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                            hoverinfo="all",
                        )
                        data_traces.append(glow_trace_amico)

                        enhanced_trace_amico = go.Scattergl(
                            x=self._coords32(amico_near["RIGHT_ASCENSION_CLUSTER"]),
                            y=self._coords32(amico_near["DECLINATION_CLUSTER"]),
                            mode="markers",
                            marker=dict(
                                size=10,
                                symbol="cross-thin",
                                line=self._line_colors(amico_near_colors),
                                opacity=1.0,
                            ),
                            name=f"AMICO (Merged, near CATRED) - {len(amico_near)} clusters",
                            legendgroup="merged_amico",
                            showlegend=False,
                            customdata=_amico_near_customdata,
                            hovertemplate=_amico_near_hovertemplate,
                            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                        )
                        data_traces.append(enhanced_trace_amico)

                    print(
                        f"Debug: Enhanced {len(pzwav_near)} PZWAV and {len(amico_near)} AMICO merged clusters near MER data"
                    )
                else:
                    # Single algorithm
                    symbol = "cross-thin" if algorithm == "AMICO" else "x-thin"

                    if algorithm.lower() == "pzwav":
                        near_catred_data = self._apply_snr_filtering(
                            near_catred_data,
                            snr_threshold_lower_pzwav,
                            snr_threshold_upper_pzwav,
                            snr_include_missing_pzwav,
                        )
                    elif algorithm.lower() == "amico":
                        near_catred_data = self._apply_snr_filtering(
                            near_catred_data,
                            snr_threshold_lower_amico,
                            snr_threshold_upper_amico,
                            snr_include_missing_amico,
                        )

                    near_colors, near_tile_ids = (
                        self._tile_colors_for(
                            near_catred_data, data_detcluster_by_cltile
                        )
                        if (show_cltile_info and data_detcluster_by_cltile)
                        else (["royalblue" if algorithm.lower() == "pzwav" else "tomato"] * len(near_catred_data), ["?"] * len(near_catred_data))
                    )
                    _near_customdata = self._cluster_customdata(near_catred_data, ( near_catred_data["DET_CODE_NB"] if has_det_code else [2 if algorithm.lower() == "pzwav" else 1] * len(near_catred_data) ), near_tile_ids)
                    _near_hovertemplate = (
                        f"<b>Cluster ({algorithm})</b><br>"
                        + "ID: %{customdata:d}<br>"
                        + "<span style='color:red'>RA: %{x:.2f}°</span><br>"
                        + "<span style='color:red'>Dec: %{y:.2f}°</span><br>"
                        + "<extra></extra>"
                    )

                    # Add glow effect trace first (background)
                    glow_trace = create_glow_trace(
                        near_catred_data["RIGHT_ASCENSION_CLUSTER"],
                        near_catred_data["DECLINATION_CLUSTER"],
                        size=28,
                        shape="circle",
                        showlegend=False,
                        name=f"{algorithm.upper()} (Merged, near CATRED)",
                    )
                    glow_trace["legendgroup"] = f"merged_{algorithm.lower()}"
                    glow_trace.update(
                        customdata=_near_customdata,
                        hovertemplate=_near_hovertemplate,
                        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                        hoverinfo="all",
                    )
                    data_traces.append(glow_trace)

                    # Add main enhanced trace (foreground)
                    enhanced_trace = go.Scattergl(
                        x=self._coords32(near_catred_data["RIGHT_ASCENSION_CLUSTER"]),
                        y=self._coords32(near_catred_data["DECLINATION_CLUSTER"]),
                        mode="markers",
                        marker=dict(
                            size=10,
                            symbol=symbol,
                            line=self._line_colors(near_colors),
                            opacity=1.0,
                        ),
                        name=f"{algorithm.upper()} (Merged, near CATRED) - {len(near_catred_data)} clusters",
                        legendgroup=f"merged_{algorithm.lower()}",
                        showlegend=False,
                        customdata=_near_customdata,
                        hovertemplate=_near_hovertemplate,
                        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial", font_color="black"),
                    )
                    data_traces.append(enhanced_trace)

                    print(
                        f"Debug: Enhanced {len(near_catred_data)} merged clusters near MER data, {len(away_from_catred_data)} normal"
                    )

    def _compute_merged_tile_colors(
        self,
        mergedcat: np.ndarray,
        data_detcluster_by_cltile: Dict[str, Any],
    ) -> Tuple[List[str], List[str]]:
        """Map each merged cluster to its source tile color and tile ID via nearest-neighbor lookup.

        Every merged cluster is guaranteed to exist in some tile, so the nearest
        neighbor IS the correct match — no tolerance gate needed.
        Uses cKDTree (scipy) for O((N+M) log N); falls back to numpy argmin.

        Returns:
            Tuple of (colors, tile_ids) — both lists of length len(mergedcat).
        """
        if len(mergedcat) == 0:
            return [], []

        _t_total = time.perf_counter()

        # Build flat arrays from all tiles
        _t = time.perf_counter()
        flat_x_pzwav: List[np.ndarray] = []
        flat_y_pzwav: List[np.ndarray] = []
        flat_tid_pzwav: List[np.ndarray] = []
        flat_x_amico: List[np.ndarray] = []
        flat_y_amico: List[np.ndarray] = []
        flat_tid_amico: List[np.ndarray] = []

        for _tile_key, value in data_detcluster_by_cltile.items():
            tile_data = value["detfits_data"]
            if len(tile_data) == 0:
                continue
            try:
                tile_id = int(value.get("tile_id", _tile_key))
            except (ValueError, TypeError):
                tile_id = 0
            tile_alg = value.get("algorithm", "PZWAV")

            ra = np.asarray(tile_data["RIGHT_ASCENSION_CLUSTER"], dtype=float)
            dec = np.asarray(tile_data["DECLINATION_CLUSTER"], dtype=float)
            x = ra * np.cos(np.deg2rad(dec))
            tid = np.full(len(tile_data), tile_id, dtype=int)

            if tile_alg == "AMICO":
                flat_x_amico.append(x)
                flat_y_amico.append(dec)
                flat_tid_amico.append(tid)
            else:
                flat_x_pzwav.append(x)
                flat_y_pzwav.append(dec)
                flat_tid_pzwav.append(tid)
        self._profiler.record("tile_colors:flat_build", time.perf_counter() - _t)

        colors: List[str] = ["gray"] * len(mergedcat)
        tile_ids: List[str] = ["?"] * len(mergedcat)
        has_det_code = "DET_CODE_NB" in mergedcat.dtype.names

        for alg_label, det_code, flat_x, flat_y, flat_tid in [
            ("PZWAV", 2, flat_x_pzwav, flat_y_pzwav, flat_tid_pzwav),
            ("AMICO", 1, flat_x_amico, flat_y_amico, flat_tid_amico),
        ]:
            if not flat_x:
                continue
            all_x = np.concatenate(flat_x)
            all_y = np.concatenate(flat_y)
            all_tid = np.concatenate(flat_tid)

            if has_det_code:
                merged_mask = mergedcat["DET_CODE_NB"] == det_code
            else:
                merged_mask = np.ones(len(mergedcat), dtype=bool)

            merged_indices = np.where(merged_mask)[0]
            if len(merged_indices) == 0:
                continue

            m_ra = np.asarray(mergedcat["RIGHT_ASCENSION_CLUSTER"][merged_mask], dtype=float)
            m_dec = np.asarray(mergedcat["DECLINATION_CLUSTER"][merged_mask], dtype=float)
            m_x = m_ra * np.cos(np.deg2rad(m_dec))

            try:
                from scipy.spatial import cKDTree
                _t = time.perf_counter()
                tree = cKDTree(np.column_stack([all_x, all_y]))
                self._profiler.record("tile_colors:kdtree_build", time.perf_counter() - _t)
                _t = time.perf_counter()
                _, idx = tree.query(np.column_stack([m_x, m_dec]))
                self._profiler.record("tile_colors:kdtree_query", time.perf_counter() - _t)
            except ImportError:
                _t = time.perf_counter()
                d2 = (m_x[:, None] - all_x[None, :]) ** 2 + (m_dec[:, None] - all_y[None, :]) ** 2
                idx = np.argmin(d2, axis=1)
                self._profiler.record("tile_colors:numpy_fallback", time.perf_counter() - _t)

            matched_tids = all_tid[idx]
            for i, tid in zip(merged_indices, matched_tids):
                tile_ids[i] = str(tid)
                try:
                    colors[i] = self.colors_list[tid]
                except IndexError:
                    colors[i] = "gray"

        self._profiler.record("tile_colors:total", time.perf_counter() - _t_total)
        return colors, tile_ids

    def _find_unmerged_mask(
        self,
        tile_data: np.ndarray,
        mergedcat: np.ndarray,
        tile_alg: Optional[str],
        angular_tolerance: float = 2.0,
        z_tolerance: float = 0.02,
    ) -> np.ndarray:
        """Return boolean mask of tile clusters NOT present in the merged catalog."""
        if len(tile_data) == 0:
            return np.zeros(0, dtype=bool)
        if len(mergedcat) == 0:
            return np.ones(len(tile_data), dtype=bool)

        has_det_code = "DET_CODE_NB" in mergedcat.dtype.names
        if has_det_code and tile_alg in ("PZWAV", "AMICO"):
            code_map = {"AMICO": 1, "PZWAV": 2}
            merged_alg = mergedcat[mergedcat["DET_CODE_NB"] == code_map[tile_alg]]
        else:
            merged_alg = mergedcat

        if len(merged_alg) == 0:
            return np.ones(len(tile_data), dtype=bool)

        tol_deg = angular_tolerance / 3600.0
        t_ra = np.asarray(tile_data["RIGHT_ASCENSION_CLUSTER"], dtype=float)
        t_dec = np.asarray(tile_data["DECLINATION_CLUSTER"], dtype=float)
        t_z = np.asarray(tile_data["Z_CLUSTER"], dtype=float)
        m_ra = np.asarray(merged_alg["RIGHT_ASCENSION_CLUSTER"], dtype=float)
        m_dec = np.asarray(merged_alg["DECLINATION_CLUSTER"], dtype=float)
        m_z = np.asarray(merged_alg["Z_CLUSTER"], dtype=float)

        try:
            from scipy.spatial import cKDTree

            # Only pairs within the angular tolerance are materialised (no dense N×M);
            # same raw (RA, Dec) metric as the dense fallback below
            pairs = cKDTree(np.column_stack([t_ra, t_dec])).sparse_distance_matrix(
                cKDTree(np.column_stack([m_ra, m_dec])), tol_deg, output_type="ndarray"
            )
            keep = np.zeros(len(t_ra), dtype=bool)
            if len(pairs):
                ti, mi = pairs["i"], pairs["j"]
                z_close = np.abs(t_z[ti] - m_z[mi]) <= z_tolerance
                keep[ti[z_close]] = True
            return ~keep
        except ImportError:
            d2 = (t_ra[:, None] - m_ra[None, :]) ** 2 + (t_dec[:, None] - m_dec[None, :]) ** 2
            ang_ok = np.sqrt(d2) <= tol_deg
            z_ok = np.abs(t_z[:, None] - m_z[None, :]) <= z_tolerance
            keep_dense: np.ndarray = np.any(ang_ok & z_ok, axis=1)
            return ~keep_dense

    def _add_unmerged_cluster_traces(
        self,
        data_traces: List,
        data: Dict[str, Any],
        datamod_detcluster_mergedcat: np.ndarray,
        snr_threshold_lower_pzwav: Optional[float],
        snr_threshold_upper_pzwav: Optional[float],
        snr_threshold_lower_amico: Optional[float],
        snr_threshold_upper_amico: Optional[float],
        z_threshold_lower: Optional[float],
        z_threshold_upper: Optional[float],
        catred_points: Optional[List] = None,
        snr_include_missing_pzwav: bool = True,
        snr_include_missing_amico: bool = True,
        z_include_missing: bool = True,
    ) -> None:
        """Add traces for per-tile clusters absent from the merged catalog."""
        for _tile_key, value in data["data_detcluster_by_cltile"].items():
            tile_data = value["detfits_data"]
            tileid = value.get("tile_id", _tile_key)
            tile_algorithm = value.get("algorithm", None)

            if tile_algorithm == "PZWAV":
                tile_data = self._apply_snr_filtering(
                    tile_data,
                    snr_threshold_lower_pzwav,
                    snr_threshold_upper_pzwav,
                    snr_include_missing_pzwav,
                )
            elif tile_algorithm == "AMICO":
                tile_data = self._apply_snr_filtering(
                    tile_data,
                    snr_threshold_lower_amico,
                    snr_threshold_upper_amico,
                    snr_include_missing_amico,
                )
            tile_data = self._apply_redshift_filtering(
                tile_data, z_threshold_lower, z_threshold_upper, z_include_missing
            )

            if len(tile_data) == 0:
                continue

            unmerged_mask = self._find_unmerged_mask(
                tile_data, datamod_detcluster_mergedcat, tile_algorithm
            )
            unmerged_data = tile_data[unmerged_mask]

            if len(unmerged_data) == 0:
                continue

            symbol = "circle-x-open" if tile_algorithm == "PZWAV" else "circle-cross-open"
            try:
                tile_color = self.colors_list[int(tileid)]
            except (IndexError, ValueError, TypeError):
                tile_color = "gray"

            has_det_code = "DET_CODE_NB" in unmerged_data.dtype.names
            det_code_values = (
                unmerged_data["DET_CODE_NB"]
                if has_det_code
                else np.full(len(unmerged_data), 2 if tile_algorithm == "PZWAV" else 1)
            )

            trace = go.Scattergl(
                x=unmerged_data["RIGHT_ASCENSION_CLUSTER"],
                y=unmerged_data["DECLINATION_CLUSTER"],
                mode="markers",
                marker=dict(
                    size=10,
                    symbol=symbol,
                    line=dict(width=2, color=tile_color),
                ),
                name=f"{tile_algorithm} Unmerged-Tile {tileid}",
                legendgroup=f"unmerged_{tile_algorithm}_{tileid}",
                showlegend=True,
                text=[
                    f"Unmerged TileID: {tileid}"
                    f"{f' ({tile_algorithm})' if tile_algorithm and data['algorithm'] == 'BOTH' else ''}"
                    f"<br>SNR_CLUSTER: {snr:.2f}<br>Z_CLUSTER: {cz:.2f}"
                    f"<br>RA: {ra:.4f}<br>Dec: {dec:.4f}"
                    for snr, cz, ra, dec in zip(
                        unmerged_data["SNR_CLUSTER"],
                        unmerged_data["Z_CLUSTER"],
                        unmerged_data["RIGHT_ASCENSION_CLUSTER"],
                        unmerged_data["DECLINATION_CLUSTER"],
                    )
                ],
                customdata=[
                    [snr, z, det_code]
                    for snr, z, det_code in zip(
                        unmerged_data["SNR_CLUSTER"],
                        unmerged_data["Z_CLUSTER"],
                        det_code_values,
                    )
                ],
                hoverinfo="text",
                hoverlabel=dict(bgcolor="lightyellow", font_size=12, font_family="Arial"),
            )
            data_traces.append(trace)
        print(f"Debug: Added unmerged cluster traces for {data['algorithm']}")

    def _create_cltile_polygons(
        self,
        polygon_traces: List,
        data: Dict[str, Any],
        tileid: str,
        tile_value: Dict[str, Any],
        show_polygons: bool,
        show_mer_tiles: bool,
        legendgroup: Optional[str] = None,
    ) -> None:
        """Create polygon traces for a single tile (LEV1, CORE, and optionally MER)."""
        # Load tile definition (cached to avoid repeated file I/O on every render)
        tile_path = tile_value["cltiledef_file"]
        if tile_path not in self._tile_def_cache:
            with open(tile_path, "r") as f:
                self._tile_def_cache[tile_path] = json.load(f)
        tile = self._tile_def_cache[tile_path]

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
            _t_mer = time.perf_counter()
            self._create_mer_tile_polygons(
                polygon_traces,
                data,
                tile,
                tileid,
                legendgroup=legendgroup if legendgroup is not None else f"cl_tile_{tileid}",
            )
            self._profiler.record("create_traces:mer_polygon_loop", time.perf_counter() - _t_mer)

    def _create_mer_tile_polygons(
        self,
        polygon_traces: List,
        data: Dict[str, Any],
        tile: Dict[str, Any],
        tileid: str,
        legendgroup: Optional[str] = None,
    ) -> None:
        """Create MER tile polygon traces for a cluster tile."""
        mer_polygons = self._mer_polygon_lookup(data)
        for mertileid in tile["LEV1"]["ID_INTERSECTED"]:
            if mertileid in mer_polygons:
                merpoly = mer_polygons[mertileid]
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

    def _mer_polygon_lookup(self, data: Dict[str, Any]) -> Dict[Any, Any]:
        """mertileid -> polygon for the catalog's dataset release, built once per catalog."""
        info = data["catred_info"]
        key = (id(info), data.get("catred_dsr"))
        cached = getattr(self, "_mer_polygon_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        rows = info[info["dataset_release"] == data.get("catred_dsr")]
        lookup = dict(zip(rows["mertileid"].tolist(), rows["polygon"].tolist()))
        self._mer_polygon_cache = (key, lookup)
        return lookup

    @staticmethod
    def _merge_polygon_traces(traces: List) -> List:
        """Join per-tile outline traces that look the same into one trace each.

        Tiles sharing a type (LEV1 / CORE / MER) and style (colour, dash, fill) become
        one trace, with NaN gaps between polygons so lines and fills stay separate.
        Names keep "Tile" + LEV1/CORE, or the "MER-Tile" prefix, which the polygon
        classifiers elsewhere rely on. Fills draw first and dashed LEV1 lines last.
        """
        groups: Dict[tuple, List] = {}
        for trace in traces:
            name = trace.name or ""
            kind = "MER" if name.startswith("MER-Tile") else ("LEV1" if "LEV1" in name else "CORE")
            line = trace.line
            key = (kind, line.color, line.dash, line.width, trace.fill, trace.fillcolor)
            groups.setdefault(key, []).append(trace)

        merged = []
        for kind in ("CORE", "MER", "LEV1"):
            for key, group in groups.items():
                if key[0] != kind:
                    continue
                if len(group) == 1:
                    merged.append(group[0])
                    continue
                xs, ys, texts = [], [], []
                for trace in group:
                    x = np.asarray(trace.x, dtype=float)
                    xs.extend([x, [np.nan]])
                    ys.extend([np.asarray(trace.y, dtype=float), [np.nan]])
                    texts.extend([trace.text] * len(x) + [None])
                label = "MER-Tile outlines" if kind == "MER" else f"Tile {kind} outlines"
                merged.append(
                    group[0].update(
                        x=np.concatenate(xs),
                        y=np.concatenate(ys),
                        text=texts,
                        name=f"{label} ({len(group)})",
                    )
                )
        return merged

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
