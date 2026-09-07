"""
Main plot callbacks for cluster visualization.

Handles primary rendering logic for the main cluster visualization plot,
including initial rendering, real-time option updates, and SNR filtering.
"""

import base64
import os
import time
import io
from typing import Optional, cast
from numpy.typing import NDArray

import dash  # type: ignore[import]
import dash_bootstrap_components as dbc  # type: ignore[import]
import numpy as np
import pandas as pd  # type: ignore[import]
import plotly.graph_objs as go  # type: ignore[import]
from dash import Input, Output, Patch, State, html

from cluster_visualization.src.visualization.sky_overview import catalog_span_deg
from cluster_visualization.src.visualization.trace_registry import TraceRegistry, TraceType

try:
    from cluster_visualization.callbacks.utils import get_idclusters_array
except ImportError:
    print("Warning: Could not import get_idclusters_array from utils. ID cluster upload functionality may be affected.")



class MainPlotCallbacks:
    """Handles main plot rendering callbacks"""

    def __init__(self, app, data_loader, catred_handler, trace_creator, figure_manager):
        """
        Initialize main plot callbacks.

        Args:
            app: Dash application instance
            data_loader: DataLoader instance for data operations
            catred_handler: CATREDHandler instance for CATRED operations
            trace_creator: TraceCreator instance for trace creation
            figure_manager: FigureManager instance for figure layout
        """
        self.app = app
        self.data_loader = data_loader
        self.catred_handler = catred_handler
        self.trace_creator = trace_creator
        self.figure_manager = figure_manager

        # Fallback attributes for backward compatibility
        self.data_cache = {}
        self.catred_traces_cache = []
        self.current_catred_data = None

        self.setup_callbacks()

    def setup_callbacks(self):
        """Setup all main plot callbacks"""
        self._setup_snr_slider_pzwav_callback()
        self._setup_snr_slider_amico_callback()
        self._setup_redshift_slider_callback()
        self._setup_richness_slider_zp_callback()
        self._setup_richness_slider_rs_callback()
        self._setup_main_render_callback()
        self._setup_apply_filters_callback()
        self._setup_options_update_callback()
        self._setup_threshold_clientside_callback()
        # self._setup_snr_pzwav_clientside_callback()
        # self._setup_snr_amico_clientside_callback()
        # self._setup_redshift_clientside_callback()
        self._setup_viewport_zoom_indicator_callback()

    def _setup_snr_slider_pzwav_callback(self):
        """Setup SNR slider initialization callback"""

        @self.app.callback(
            [
                Output("snr-range-slider-pzwav", "min"),
                Output("snr-range-slider-pzwav", "max"),
                Output("snr-range-slider-pzwav", "value"),
                Output("snr-range-slider-pzwav", "marks"),
                Output("snr-range-slider-pzwav", "disabled"),
                Output("snr-include-missing-pzwav", "disabled"),
                Output("snr-include-missing-pzwav", "label"),
            ],
            [Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def update_snr_slider_pzwav(algorithm):
            try:
                # Load data to get SNR range
                data = self.load_data(algorithm)
                snr_min = data["snr_min_pzwav"]
                snr_max = data["snr_max_pzwav"]

                # Create marks at key points
                marks = {snr_min: f"{snr_min:.1f}", snr_max: f"{snr_max:.1f}"}

                # Default to full range
                default_value = [snr_min, snr_max]

                switch = self._missing_switch_state(
                    data, "SNR_CLUSTER", "SNR", det_code=2, tile_algorithm="PZWAV"
                )
                return (snr_min, snr_max, default_value, marks, False, *switch)

            except Exception as e:
                # Fallback values if data loading fails
                return (
                    0,
                    100,
                    [0, 100],
                    {0: "0", 100: "100"},
                    True,
                    False,
                    "Include clusters with missing SNR",
                )

    def _setup_snr_slider_amico_callback(self):
        """Setup SNR slider initialization callback"""

        @self.app.callback(
            [
                Output("snr-range-slider-amico", "min"),
                Output("snr-range-slider-amico", "max"),
                Output("snr-range-slider-amico", "value"),
                Output("snr-range-slider-amico", "marks"),
                Output("snr-range-slider-amico", "disabled"),
                Output("snr-include-missing-amico", "disabled"),
                Output("snr-include-missing-amico", "label"),
            ],
            [Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def update_snr_slider_amico(algorithm):
            try:
                # Load data to get SNR range
                data = self.load_data(algorithm)
                snr_min = data["snr_min_amico"]
                snr_max = data["snr_max_amico"]

                # Create marks at key points
                marks = {snr_min: f"{snr_min:.1f}", snr_max: f"{snr_max:.1f}"}

                # Default to full range
                default_value = [snr_min, snr_max]

                switch = self._missing_switch_state(
                    data, "SNR_CLUSTER", "SNR", det_code=1, tile_algorithm="AMICO"
                )
                return (snr_min, snr_max, default_value, marks, False, *switch)

            except Exception as e:
                # Fallback values if data loading fails
                return (
                    0,
                    100,
                    [0, 100],
                    {0: "0", 100: "100"},
                    True,
                    False,
                    "Include clusters with missing SNR",
                )

    def _setup_redshift_slider_callback(self):
        """Setup redshift slider initialization callback"""

        @self.app.callback(
            [
                Output("redshift-range-slider", "min"),
                Output("redshift-range-slider", "max"),
                Output("redshift-range-slider", "value"),
                Output("redshift-range-slider", "marks"),
                Output("redshift-range-slider", "disabled"),
                Output("redshift-include-missing", "disabled"),
                Output("redshift-include-missing", "label"),
            ],
            [Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def update_redshift_slider(algorithm):
            try:
                # Load data to get redshift range
                data = self.load_data(algorithm)
                z_min = data["z_min"]
                z_max = data["z_max"]

                # Create marks at key points
                marks = {z_min: f"{z_min:.1f}", z_max: f"{z_max:.1f}"}

                # Default to full range
                default_value = [z_min, z_max]

                switch = self._missing_switch_state(data, "Z_CLUSTER", "redshift")
                return (z_min, z_max, default_value, marks, False, *switch)

            except Exception as e:
                # Fallback values if data loading fails
                return (
                    0,
                    10,
                    [0, 10],
                    {0: "0", 10: "10"},
                    True,
                    False,
                    "Include clusters with missing redshift",
                )

    @staticmethod
    def _has_missing_values(data, column, det_code=None, tile_algorithm=None):
        """True if any loaded cluster lacks ``column`` (NaN).

        Checks the merged catalog (restricted to ``DET_CODE_NB == det_code`` when that
        column exists) and the per-tile catalogs (restricted to ``tile_algorithm``),
        since the "include missing" switches also filter the unmerged tile clusters.
        """
        merged = data.get("data_detcluster_mergedcat")
        if merged is not None and column in (merged.dtype.names or ()):
            rows = merged
            if det_code is not None and "DET_CODE_NB" in merged.dtype.names:
                rows = merged[merged["DET_CODE_NB"] == det_code]
            if len(rows) and np.isnan(np.asarray(rows[column], dtype=float)).any():
                return True

        for tile in (data.get("data_detcluster_by_cltile") or {}).values():
            if tile_algorithm is not None and tile.get("algorithm", tile_algorithm) != tile_algorithm:
                continue
            tile_data = tile.get("detfits_data")
            dtype = getattr(tile_data, "dtype", None)
            if tile_data is None or dtype is None or column not in (dtype.names or ()):
                continue
            if len(tile_data) and np.isnan(np.asarray(tile_data[column], dtype=float)).any():
                return True
        return False

    def _missing_switch_state(self, data, column, quantity, det_code=None, tile_algorithm=None):
        """(disabled, label) for an "Include clusters with missing <quantity>" switch."""
        label = f"Include clusters with missing {quantity}"
        if self._has_missing_values(data, column, det_code=det_code, tile_algorithm=tile_algorithm):
            return False, label
        return True, f"{label} (none missing)"

    def _setup_richness_slider_zp_callback(self):
        @self.app.callback(
            [
                Output("richness-range-slider-zp", "min"),
                Output("richness-range-slider-zp", "max"),
                Output("richness-range-slider-zp", "value"),
                Output("richness-range-slider-zp", "marks"),
                Output("richness-range-slider-zp", "disabled"),
            ],
            [Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def update_richness_slider_zp(algorithm):
            try:
                data = self.load_data(algorithm)
                r_min = data["richness_zp_min"]
                r_max = data["richness_zp_max"]
                if r_min is None or r_max is None:
                    raise ValueError("richness_zp not available")
                mark_min_zp = r_min if r_min != 0.0 else 0.001
                mark_max_zp = r_max
                marks = {mark_min_zp: f"{r_min:.1f}", mark_max_zp: f"{r_max:.1f}"}
                return r_min, r_max, [r_min, r_max], marks, False
            except Exception:
                return (
                    0, 100, [0, 100], {0.001: "0", 100: "100"}, 
                    True,
                )

    def _setup_richness_slider_rs_callback(self):
        @self.app.callback(
            [
                Output("richness-range-slider-rs", "min"),
                Output("richness-range-slider-rs", "max"),
                Output("richness-range-slider-rs", "value"),
                Output("richness-range-slider-rs", "marks"),
                Output("richness-range-slider-rs", "disabled"),
            ],
            [Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def update_richness_slider_rs(algorithm):
            try:
                data = self.load_data(algorithm)
                r_min = data["richness_rs_min"]
                r_max = data["richness_rs_max"]
                if r_min is None or r_max is None:
                    raise ValueError("richness_rs not available")
                mark_min_rs = r_min if r_min != 0.0 else 0.001
                mark_max_rs = r_max
                marks = {mark_min_rs: f"{r_min:.1f}", mark_max_rs: f"{r_max:.1f}"}
                return r_min, r_max, [r_min, r_max], marks, False
            except Exception:
                return (
                    0, 100, [0, 100], {0.001: "0", 100: "100"},
                    True,
                )

    def _setup_main_render_callback(self):
        """Setup main rendering callback for initial plot and SNR/redshift filtering"""

        @self.app.callback(
            [
                Output("cluster-plot", "figure"),
                Output("phz-pdf-plot", "figure"),
                Output("status-info", "children"),
                Output("rendered-meta-store", "data"),
            ],
            [
                # Full renders only; same-algorithm Re-renders are routed to the patch path
                Input("render-full-request", "data"),
            ],
            [
                State("algorithm-dropdown", "value"),
                State("matching-clusters-switch", "value"),
                State("snr-range-slider-pzwav", "value"),
                State("snr-range-slider-amico", "value"),
                State("snr-include-missing-pzwav", "value"),
                State("snr-include-missing-amico", "value"),
                State("redshift-range-slider", "value"),
                State("redshift-include-missing", "value"),
                State("richness-range-slider-zp", "value"),
                State("richness-range-slider-rs", "value"),
                State("richness-include-missing-zp", "value"),
                State("richness-include-missing-rs", "value"),
                State("richness-mode-radio", "value"),
                State("flag-quality-zp-checklist", "value"),
                State("flag-quality-rs-checklist", "value"),
                State("idcluster-upload", "contents"),
                State("idcluster-upload", "filename"),
                State("ned-specz-filter-switch", "value"),
                State("polygon-switch", "value"),
                State("mer-switch", "value"),
                State("aspect-ratio-switch", "value"),
                State("unmerged-clusters-switch", "value"),
                State("cltile-info-switch", "value"),
                State("catred-mode-switch", "value"),
                State("catred-threshold-slider", "value"),
                State("magnitude-limit-slider", "value"),
                State("cluster-plot", "relayoutData"),
                State("cluster-plot", "figure"),
                State("selected-cluster-box-coords", "data"),
                State("view-bounds-store", "data"),
            ],
            background=True,
            running=[
                (Output("data-load-progress-container", "style"), {"display": "block"}, {"display": "none"}),
                (Output("render-button", "disabled"), True, False),
            ],
            progress=[
                Output("data-load-progress", "value"),
                Output("data-load-label", "children"),
            ],
        )
        def update_plot(
            set_progress,
            n_clicks,
            algorithm,
            matching_clusters,
            snr_range_pzwav,
            snr_range_amico,
            snr_include_missing_pzwav,
            snr_include_missing_amico,
            redshift_range,
            redshift_include_missing,
            richness_range_zp,
            richness_range_rs,
            richness_include_missing_zp,
            richness_include_missing_rs,
            richness_mode,
            flag_quality_zp,
            flag_quality_rs,
            idcluster_upload_contents,
            idcluster_upload_filename,
            ned_specz_filter,
            show_polygons,
            show_mer_tiles,
            free_aspect_ratio,
            show_unmerged_clusters,
            show_cltile_info,
            catred_masked,
            threshold,
            maglim,
            relayout_data,
            current_figure,
            box_coords,
            view_store,
        ):
            # Only render once the button has been clicked
            if not n_clicks:
                return (*self._create_initial_empty_plots(free_aspect_ratio), None)

            try:
                set_progress((5, f"Preparing {algorithm} data..."))
                if idcluster_upload_contents and idcluster_upload_filename:
                    set_progress((10, f"Processing uploaded cluster IDs from {idcluster_upload_filename}..."))
                kw = self._resolve_filter_kwargs(
                    snr_range_pzwav, snr_range_amico,
                    snr_include_missing_pzwav, snr_include_missing_amico,
                    redshift_range, redshift_include_missing,
                    richness_range_zp, richness_range_rs,
                    richness_include_missing_zp, richness_include_missing_rs,
                    richness_mode, flag_quality_zp, flag_quality_rs,
                    idcluster_upload_contents, idcluster_upload_filename,
                    ned_specz_filter=ned_specz_filter,
                )

                # Load data for selected algorithm
                set_progress((20, f"Loading {algorithm} catalog..."))
                data = self.load_data(algorithm)
                view_bounds, cull = self._cull_settings(data, view_store)

                # Keep CATRED / mosaic / mask / NED spec-z overlays and cluster members across renders
                preserved = TraceRegistry.extract_traces(
                    current_figure,
                    {
                        TraceType.CATRED,
                        TraceType.MOSAIC,
                        TraceType.MASK_OVERLAY,
                        TraceType.NED_SPECZ,
                        TraceType.MEMBERS,
                    },
                )

                set_progress((55, "Creating visualization traces..."))
                traces = self.create_traces(
                    data,
                    show_polygons,
                    show_mer_tiles,
                    relayout_data,
                    catred_masked,
                    existing_catred_traces=preserved[TraceType.CATRED],
                    existing_mosaic_traces=preserved[TraceType.MOSAIC],
                    existing_mask_overlay_traces=preserved[TraceType.MASK_OVERLAY],
                    existing_ned_specz_traces=preserved[TraceType.NED_SPECZ],
                    threshold=threshold,
                    maglim=maglim,
                    show_unmerged_clusters=show_unmerged_clusters,
                    matching_clusters=matching_clusters,
                    show_cltile_info=show_cltile_info,
                    view_bounds=view_bounds,
                    **kw,
                )
                # Members stay the top layer, as after "Show members"
                traces = list(traces) + list(preserved[TraceType.MEMBERS])

                # Create figure
                set_progress((80, "Building figure..."))
                fig = (
                    self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio)
                    if self.figure_manager
                    else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                )

                # Re-inject mosaic layout.images from previous figure
                if current_figure and isinstance(current_figure, dict):
                    prev_images = current_figure.get("layout", {}).get("images") or []
                    mosaic_images = [
                        img for img in prev_images
                        if isinstance(img, dict) and img.get("name", "").startswith("Mosaic")
                    ]
                    if mosaic_images:
                        existing_layout_images = list(fig.layout.images or [])
                        fig.update_layout(images=existing_layout_images + mosaic_images)

                # Preserve zoom state only when current figure has actual data (skip on initial render)
                has_existing_data = (
                    current_figure is not None
                    and isinstance(current_figure, dict)
                    and len(current_figure.get("data", [])) > 0
                )
                if has_existing_data:
                    if self.figure_manager:
                        self.figure_manager.preserve_zoom_state(fig, relayout_data, current_figure)
                    else:
                        self._preserve_zoom_state_fallback(fig, relayout_data, current_figure)

                status = self._filtered_status(
                    algorithm, data, kw, show_polygons, show_mer_tiles, free_aspect_ratio
                )

                # Create empty PHZ_PDF plot
                empty_phz_fig = self._create_empty_phz_plot()

                if box_coords:
                    fig.add_trace(self._selected_cluster_marker(box_coords))

                self._log_figure_size(fig, data)
                # rendered_at marks a full Render: the globe/map switcher picks the
                # starting view only then, from the catalog's span
                return fig, empty_phz_fig, status, {
                    "algorithm": algorithm, "cull": cull, "rendered_at": time.time(),
                    "span": catalog_span_deg(data),
                }

            except Exception as e:
                return (*self._create_error_plots(str(e)), dash.no_update)

    # ------------------------------------------------------------------
    # Shared render helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _viewport_ack(triggered_id, viewport_request):
        """viewport-ack payload. `id` is the viewport request this run answers (None for
        Apply / Re-render runs), so the browser only ends the request it is waiting for.
        `t` makes every ack a new value, so the tracker always runs."""
        req_id = viewport_request if triggered_id == "viewport-request" else None
        return {"id": req_id, "t": time.time()}

    def _cull_settings(self, data, view_store):
        """(view_bounds, cull) for a render.

        Culling is on for catalogs above [view] cull_min_clusters merged clusters
        (config.ini, default 5000); smaller catalogs are sent whole so zooming never
        needs a server trip.
        The bounds are the window the browser recorded as sent (view-bounds-store).
        """
        merged = data.get("data_detcluster_mergedcat") if isinstance(data, dict) else None
        n = len(merged) if merged is not None else 0
        # From the app's TraceCreator (configured from config.ini at startup)
        cull_min = self.trace_creator.cull_min_clusters() if self.trace_creator is not None else 5000
        cull = n > cull_min
        sent = (view_store or {}).get("sent") if cull else None
        bounds = tuple(float(v) for v in sent) if sent and len(sent) == 4 else None
        return bounds, cull

    @staticmethod
    def _resolve_filter_kwargs(
        snr_range_pzwav, snr_range_amico,
        snr_include_missing_pzwav, snr_include_missing_amico,
        redshift_range, redshift_include_missing,
        richness_range_zp, richness_range_rs,
        richness_include_missing_zp, richness_include_missing_rs,
        richness_mode, flag_quality_zp, flag_quality_rs,
        idcluster_upload_contents, idcluster_upload_filename,
        ned_specz_filter=False,
    ):
        """Turn raw filter control values into create_traces / create_cluster_traces kwargs."""

        def bounds(value):
            return (value[0], value[1]) if value and len(value) == 2 else (None, None)

        snr_pzwav_lower, snr_pzwav_upper = bounds(snr_range_pzwav)
        snr_amico_lower, snr_amico_upper = bounds(snr_range_amico)
        z_lower, z_upper = bounds(redshift_range)

        if richness_mode == "zp":
            richness_lower, richness_upper = bounds(richness_range_zp)
            richness_include_missing = richness_include_missing_zp
        elif richness_mode == "rs":
            richness_lower, richness_upper = bounds(richness_range_rs)
            richness_include_missing = richness_include_missing_rs
        else:
            richness_lower = richness_upper = None
            richness_include_missing = True

        idcluster_list = None
        if idcluster_upload_contents and idcluster_upload_filename:
            idcluster_list = get_idclusters_array(idcluster_upload_contents, idcluster_upload_filename)

        return dict(
            snr_threshold_lower_pzwav=snr_pzwav_lower,
            snr_threshold_upper_pzwav=snr_pzwav_upper,
            snr_threshold_lower_amico=snr_amico_lower,
            snr_threshold_upper_amico=snr_amico_upper,
            snr_include_missing_pzwav=snr_include_missing_pzwav,
            snr_include_missing_amico=snr_include_missing_amico,
            z_threshold_lower=z_lower,
            z_threshold_upper=z_upper,
            z_include_missing=redshift_include_missing,
            richness_threshold_lower=richness_lower,
            richness_threshold_upper=richness_upper,
            richness_mode=richness_mode,
            richness_include_missing=richness_include_missing,
            flag_quality_zp=flag_quality_zp,
            flag_quality_rs=flag_quality_rs,
            idcluster_list=idcluster_list,
            ned_specz_filter=bool(ned_specz_filter),
        )

    def _filtered_status(self, algorithm, data, kw, show_polygons, show_mer_tiles, free_aspect_ratio):
        """Status toast with the filtered merged-cluster count for the given filter kwargs."""
        merged = data["data_detcluster_mergedcat"]
        if algorithm == "BOTH":
            filtered_merged_count = self._calculate_filtered_count_both(
                merged,
                kw["snr_threshold_lower_pzwav"],
                kw["snr_threshold_upper_pzwav"],
                kw["snr_threshold_lower_amico"],
                kw["snr_threshold_upper_amico"],
                kw["z_threshold_lower"],
                kw["z_threshold_upper"],
                snr_include_missing_pzwav=kw["snr_include_missing_pzwav"],
                snr_include_missing_amico=kw["snr_include_missing_amico"],
                z_include_missing=kw["z_include_missing"],
            )
            lp, la = kw["snr_threshold_lower_pzwav"], kw["snr_threshold_lower_amico"]
            up, ua = kw["snr_threshold_upper_pzwav"], kw["snr_threshold_upper_amico"]
            snr_lower_display = (
                f"PZWAV: {lp:.2f}, AMICO: {la:.2f}" if lp is not None and la is not None else None
            )
            snr_upper_display = (
                f"PZWAV: {up:.2f}, AMICO: {ua:.2f}" if up is not None and ua is not None else None
            )
        else:
            suffix = "pzwav" if algorithm == "PZWAV" else "amico"
            snr_lower_display = kw[f"snr_threshold_lower_{suffix}"]
            snr_upper_display = kw[f"snr_threshold_upper_{suffix}"]
            filtered_merged_count = self._calculate_filtered_count(
                merged,
                snr_lower_display,
                snr_upper_display,
                kw["z_threshold_lower"],
                kw["z_threshold_upper"],
                snr_include_missing=kw[f"snr_include_missing_{suffix}"],
                z_include_missing=kw["z_include_missing"],
            )

        return self._create_status_info(
            algorithm,
            data,
            filtered_merged_count,
            snr_lower_display,
            snr_upper_display,
            kw["z_threshold_lower"],
            kw["z_threshold_upper"],
            show_polygons,
            show_mer_tiles,
            free_aspect_ratio,
            "success",
        )

    @staticmethod
    def _selected_cluster_marker(box_coords):
        """Yellow square marking the cluster selected in the action modal."""
        return go.Scatter(
            x=[box_coords["ra"]],
            y=[box_coords["dec"]],
            mode="markers",
            marker=dict(symbol="square-open", size=18, color="yellow", line=dict(color="yellow", width=2)),
            name="__selected_cluster__",
            showlegend=False,
            hoverinfo="skip",
        )

    @staticmethod
    def _log_figure_size(fig, data):
        """Debug log of the serialized figure size; serializing is costly, so opt-in only."""
        if os.environ.get("CLUSTERVIZ_LOG_FIGURE_SIZE") != "1":
            return
        _fig_json = fig.to_json()
        print(
            f"Debug: Figure JSON {len(_fig_json) / 1024:.0f} KB, {len(fig.data)} traces, "
            f"{len(data['data_detcluster_mergedcat'])} merged clusters"
        )

    def _shared_catred_points(self):
        """CATRED (ra, dec) points persisted by the last render, for near-CATRED markers.

        The incremental Apply path does not receive the figure, so it reads the
        CATRED data that create_traces writes to the shared state cache.
        """
        try:
            import diskcache as _dc

            state_dir = os.path.join(os.path.expanduser("~"), ".cache", "clusterviz_state")
            with _dc.Cache(state_dir) as cache:
                catred_data = cache.get("catred_click_data")
        except Exception as exc:
            print(f"Warning: Could not read CATRED state cache: {exc}")
            return None

        points = []
        for entry in (catred_data or {}).values():
            if entry and entry.get("ra"):
                points.extend(zip(entry["ra"], entry["dec"]))
        return points or None

    def _setup_apply_filters_callback(self):
        """Incremental re-render for "Apply filters".

        Runs in the main server process (warm data cache, no background fork), rebuilds
        only the filter-dependent cluster traces and patches them into the figure.
        Polygons, CATRED, mosaic and mask overlays are left untouched in the browser.
        """

        @self.app.callback(
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("status-info", "children", allow_duplicate=True),
                Output("rendered-meta-store", "data", allow_duplicate=True),
                # Tells the browser's viewport tracker this answer has arrived (always a
                # new value, so the tracker runs even when the figure summary is unchanged)
                Output("viewport-ack", "data"),
            ],
            [
                Input("apply-filters-button", "n_clicks"),
                # Re-render with an unchanged algorithm takes the same incremental path
                Input("render-patch-request", "data"),
                # Zoom/pan left the area whose clusters were sent: re-cull
                Input("viewport-request", "data"),
            ],
            [
                State("algorithm-dropdown", "value"),
                State("matching-clusters-switch", "value"),
                State("snr-range-slider-pzwav", "value"),
                State("snr-range-slider-amico", "value"),
                State("snr-include-missing-pzwav", "value"),
                State("snr-include-missing-amico", "value"),
                State("redshift-range-slider", "value"),
                State("redshift-include-missing", "value"),
                State("richness-range-slider-zp", "value"),
                State("richness-range-slider-rs", "value"),
                State("richness-include-missing-zp", "value"),
                State("richness-include-missing-rs", "value"),
                State("richness-mode-radio", "value"),
                State("flag-quality-zp-checklist", "value"),
                State("flag-quality-rs-checklist", "value"),
                State("idcluster-upload", "contents"),
                State("idcluster-upload", "filename"),
                State("ned-specz-filter-switch", "value"),
                State("polygon-switch", "value"),
                State("mer-switch", "value"),
                State("aspect-ratio-switch", "value"),
                State("unmerged-clusters-switch", "value"),
                State("cltile-info-switch", "value"),
                State("catred-mode-switch", "value"),
                State("cluster-plot", "relayoutData"),
                State("selected-cluster-box-coords", "data"),
                State("rendered-meta-store", "data"),
                State("cluster-trace-index-store", "data"),
                State("view-bounds-store", "data"),
            ],
            prevent_initial_call=True,
        )
        def apply_filters(
            n_clicks,
            patch_request,
            viewport_request,
            algorithm,
            matching_clusters,
            snr_range_pzwav,
            snr_range_amico,
            snr_include_missing_pzwav,
            snr_include_missing_amico,
            redshift_range,
            redshift_include_missing,
            richness_range_zp,
            richness_range_rs,
            richness_include_missing_zp,
            richness_include_missing_rs,
            richness_mode,
            flag_quality_zp,
            flag_quality_rs,
            idcluster_upload_contents,
            idcluster_upload_filename,
            ned_specz_filter,
            show_polygons,
            show_mer_tiles,
            free_aspect_ratio,
            show_unmerged_clusters,
            show_cltile_info,
            catred_masked,
            relayout_data,
            box_coords,
            rendered_meta,
            trace_index,
            view_store,
        ):
            if not n_clicks and not patch_request and not viewport_request:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update

            ack = self._viewport_ack(dash.callback_context.triggered_id, viewport_request)
            tag = f"viewport #{ack['id']}" if ack["id"] is not None else "apply"
            _t_total = time.perf_counter()
            try:
                kw = self._resolve_filter_kwargs(
                    snr_range_pzwav, snr_range_amico,
                    snr_include_missing_pzwav, snr_include_missing_amico,
                    redshift_range, redshift_include_missing,
                    richness_range_zp, richness_range_rs,
                    richness_include_missing_zp, richness_include_missing_rs,
                    richness_mode, flag_quality_zp, flag_quality_rs,
                    idcluster_upload_contents, idcluster_upload_filename,
                    ned_specz_filter=ned_specz_filter,
                )
                _t_load = time.perf_counter()
                data = self.load_data(algorithm)
                view_bounds, cull = self._cull_settings(data, view_store)
                _dt_load = time.perf_counter() - _t_load

                can_patch = bool(
                    self.trace_creator is not None
                    and rendered_meta
                    and rendered_meta.get("algorithm") == algorithm
                    and trace_index
                    and trace_index.get("n", 0) > 0
                )

                if not can_patch:
                    # Figure on screen is not this algorithm's (or unknown): rebuild in full
                    print("Debug: Apply filters - full rebuild (no patchable render on screen)")
                    traces = self.create_traces(
                        data,
                        show_polygons,
                        show_mer_tiles,
                        relayout_data,
                        catred_masked,
                        show_unmerged_clusters=show_unmerged_clusters,
                        matching_clusters=matching_clusters,
                        show_cltile_info=show_cltile_info,
                        view_bounds=view_bounds,
                        **kw,
                    )
                    fig = (
                        self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio)
                        if self.figure_manager
                        else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                    )
                    if self.figure_manager:
                        self.figure_manager.preserve_zoom_state(fig, relayout_data, None)
                    if box_coords:
                        fig.add_trace(self._selected_cluster_marker(box_coords))
                    status = self._filtered_status(
                        algorithm, data, kw, show_polygons, show_mer_tiles, free_aspect_ratio
                    )
                    return fig, status, {"algorithm": algorithm, "cull": cull}, ack

                # Incremental: rebuild only the cluster traces
                self.trace_creator.proximity_detector.clear_bounds_cache()
                catred_points = self._shared_catred_points() if trace_index.get("has_catred") else None

                _t = time.perf_counter()
                cluster_traces = self.trace_creator.create_cluster_traces(
                    data,
                    relayout_data=relayout_data,
                    catred_points=catred_points,
                    show_unmerged_clusters=show_unmerged_clusters,
                    matching_clusters=matching_clusters,
                    show_cltile_info=show_cltile_info,
                    view_bounds=view_bounds,
                    **kw,
                )
                if box_coords:
                    cluster_traces.append(self._selected_cluster_marker(box_coords))
                _dt_traces = time.perf_counter() - _t
                self.trace_creator._profiler.record("apply:cluster_traces", _dt_traces)

                # Replace the old cluster traces: remove from the end so indices stay valid,
                # then append, keeping clusters as the top layer like a full render
                _t = time.perf_counter()
                patch = Patch()
                for index in sorted(trace_index.get("cluster", []), reverse=True):
                    patch["data"].__delitem__(index)
                # Via Figure.to_dict so numpy arrays are sent as typed binary (Plotly 6);
                # a bare trace.to_plotly_json() would serialise them as JSON lists
                patch["data"].extend(go.Figure(data=cluster_traces).to_dict()["data"])
                _dt_patch = time.perf_counter() - _t
                self.trace_creator._profiler.record("apply:patch", _dt_patch)

                status = self._filtered_status(
                    algorithm, data, kw, show_polygons, show_mer_tiles, free_aspect_ratio
                )
                self.trace_creator._profiler.record("apply:total", time.perf_counter() - _t_total)
                cull_info = getattr(self.trace_creator, "last_cull", None) or {}
                shown = (
                    "density map" if cull_info.get("density")
                    else f"{cull_info.get('clusters', '?')} clusters, margin {cull_info.get('margin')}"
                ) if view_bounds is not None else "whole catalog"
                print(
                    f"Patch [{tag}] ({shown}): {len(cluster_traces)} traces in {time.perf_counter() - _t_total:.2f}s "
                    f"[load {_dt_load:.2f}s, traces {_dt_traces:.2f}s, encode {_dt_patch:.2f}s]"
                )
                return patch, status, dash.no_update, ack

            except Exception as e:
                import traceback

                print(f"❌ Patch [{tag}] failed: {e}")
                traceback.print_exc()
                _fig, _phz, status = self._create_error_plots(str(e))
                # Still acknowledge, so the browser stops waiting for this request
                return dash.no_update, status, dash.no_update, ack

    def _setup_options_update_callback(self):
        """Setup real-time options update callback (preserves zoom)"""

        @self.app.callback(
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("phz-pdf-plot", "figure", allow_duplicate=True),
                Output("status-info", "children", allow_duplicate=True),
                Output("rendered-meta-store", "data", allow_duplicate=True),
            ],
            [
                Input("algorithm-dropdown", "value"),
                Input("polygon-switch", "value"),
                Input("mer-switch", "value"),
                Input("aspect-ratio-switch", "value"),
                Input("unmerged-clusters-switch", "value"),
                Input("cltile-info-switch", "value"),
                Input("catred-mode-switch", "value"),
            ],
            [
                State("render-button", "n_clicks"),
                State("matching-clusters-switch", "value"),
                State("snr-range-slider-pzwav", "value"),
                State("snr-range-slider-amico", "value"),
                State("redshift-range-slider", "value"),
                State("richness-range-slider-zp", "value"),
                State("richness-range-slider-rs", "value"),
                State("flag-quality-zp-checklist", "value"),
                State("flag-quality-rs-checklist", "value"),
                State("idcluster-upload", "contents"),
                State("idcluster-upload", "filename"),
                State("catred-threshold-slider", "value"),
                State("magnitude-limit-slider", "value"),
                State("cluster-plot", "relayoutData"),
                State("cluster-plot", "figure"),
                State("selected-cluster-box-coords", "data"),
                State("richness-mode-radio", "value"),
                State("snr-include-missing-pzwav", "value"),
                State("snr-include-missing-amico", "value"),
                State("redshift-include-missing", "value"),
                State("richness-include-missing-zp", "value"),
                State("richness-include-missing-rs", "value"),
                State("ned-specz-filter-switch", "value"),
                State("applied-filters-store", "data"),
                State("view-bounds-store", "data"),
            ],
            prevent_initial_call=True,
        )
        def update_plot_options(
            algorithm,
            show_polygons,
            show_mer_tiles,
            free_aspect_ratio,
            show_unmerged_clusters,
            show_cltile_info,
            catred_masked,
            n_clicks,
            matching_clusters,
            snr_range_pzwav,
            snr_range_amico,
            redshift_range,
            richness_range_zp,
            richness_range_rs,
            flag_quality_zp,
            flag_quality_rs,
            idcluster_upload_contents,
            idcluster_upload_filename,
            threshold,
            maglim,
            relayout_data,
            current_figure,
            box_coords,
            richness_mode,
            snr_include_missing_pzwav,
            snr_include_missing_amico,
            redshift_include_missing,
            richness_include_missing_zp,
            richness_include_missing_rs,
            ned_specz_filter,
            applied_filters,
            view_store,
        ):
            # Only update if render button has been clicked at least once
            if n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update

            # Filters change the plot only via Apply filters: redraw display options
            # with the filter values of the last render, not the controls' pending values
            if applied_filters:
                matching_clusters = applied_filters.get("matching-clusters-switch", matching_clusters)
                snr_range_pzwav = applied_filters.get("snr-range-slider-pzwav", snr_range_pzwav)
                snr_range_amico = applied_filters.get("snr-range-slider-amico", snr_range_amico)
                redshift_range = applied_filters.get("redshift-range-slider", redshift_range)
                richness_range_zp = applied_filters.get("richness-range-slider-zp", richness_range_zp)
                richness_range_rs = applied_filters.get("richness-range-slider-rs", richness_range_rs)
                flag_quality_zp = applied_filters.get("flag-quality-zp-checklist", flag_quality_zp)
                flag_quality_rs = applied_filters.get("flag-quality-rs-checklist", flag_quality_rs)
                richness_mode = applied_filters.get("richness-mode-radio", richness_mode)
                snr_include_missing_pzwav = applied_filters.get(
                    "snr-include-missing-pzwav", snr_include_missing_pzwav
                )
                snr_include_missing_amico = applied_filters.get(
                    "snr-include-missing-amico", snr_include_missing_amico
                )
                redshift_include_missing = applied_filters.get(
                    "redshift-include-missing", redshift_include_missing
                )
                richness_include_missing_zp = applied_filters.get(
                    "richness-include-missing-zp", richness_include_missing_zp
                )
                richness_include_missing_rs = applied_filters.get(
                    "richness-include-missing-rs", richness_include_missing_rs
                )
                ned_specz_filter = applied_filters.get("ned-specz-filter-switch", ned_specz_filter)
                if applied_filters.get("idcluster-upload") is None:
                    idcluster_upload_contents = None

            try:
                # Extract SNR values from range sliders (separate for PZWAV and AMICO)
                snr_pzwav_lower = (
                    snr_range_pzwav[0] if snr_range_pzwav and len(snr_range_pzwav) == 2 else None
                )
                snr_pzwav_upper = (
                    snr_range_pzwav[1] if snr_range_pzwav and len(snr_range_pzwav) == 2 else None
                )

                snr_amico_lower = (
                    snr_range_amico[0] if snr_range_amico and len(snr_range_amico) == 2 else None
                )
                snr_amico_upper = (
                    snr_range_amico[1] if snr_range_amico and len(snr_range_amico) == 2 else None
                )

                # Determine which SNR range to use based on algorithm
                if algorithm == "PZWAV":
                    snr_lower = snr_pzwav_lower
                    snr_upper = snr_pzwav_upper
                elif algorithm == "AMICO":
                    snr_lower = snr_amico_lower
                    snr_upper = snr_amico_upper
                else:  # BOTH
                    snr_lower = (snr_pzwav_lower, snr_amico_lower)
                    snr_upper = (snr_pzwav_upper, snr_amico_upper)

                # Extract redshift values from range slider
                z_lower = redshift_range[0] if redshift_range and len(redshift_range) == 2 else None
                z_upper = redshift_range[1] if redshift_range and len(redshift_range) == 2 else None

                # Extract richness values based on selected mode
                if richness_mode == "zp" and richness_range_zp and len(richness_range_zp) == 2:
                    richness_lower = richness_range_zp[0]
                    richness_upper = richness_range_zp[1]
                elif richness_mode == "rs" and richness_range_rs and len(richness_range_rs) == 2:
                    richness_lower = richness_range_rs[0]
                    richness_upper = richness_range_rs[1]
                else:
                    richness_lower = None
                    richness_upper = None

                if richness_mode == "zp":
                    richness_include_missing = richness_include_missing_zp
                elif richness_mode == "rs":
                    richness_include_missing = richness_include_missing_rs
                else:
                    richness_include_missing = True

                # Process uploaded ID cluster list if provided
                if idcluster_upload_contents:
                    idcluster_list = get_idclusters_array(idcluster_upload_contents, idcluster_upload_filename)
                else:
                    idcluster_list = None


                # Load data for selected algorithm
                data = self.load_data(algorithm)
                view_bounds, cull = self._cull_settings(data, view_store)

                # Extract existing traces to preserve across re-render
                _preserved = TraceRegistry.extract_traces(
                    current_figure,
                    {
                        TraceType.CATRED,
                        TraceType.MOSAIC,
                        TraceType.MASK_OVERLAY,
                        TraceType.NED_SPECZ,
                        TraceType.NED_NEARBY_CATRED,
                    },
                )
                existing_catred_traces = _preserved[TraceType.CATRED]
                existing_mosaic_traces = _preserved[TraceType.MOSAIC]
                existing_mask_overlay_traces = _preserved[TraceType.MASK_OVERLAY]
                existing_ned_specz_traces = _preserved[TraceType.NED_SPECZ]
                existing_ned_nearby_catred_traces = _preserved[TraceType.NED_NEARBY_CATRED]

                print(
                    f"Debug: Options update - preserving {len(existing_catred_traces)} CATRED, "
                    f"{len(existing_mosaic_traces)} Mosaic, {len(existing_mask_overlay_traces)} Mask traces"
                )

                # Create traces with existing CATRED traces preserved and separate SNR thresholds
                traces = self.create_traces(
                    data,
                    show_polygons,
                    show_mer_tiles,
                    relayout_data,
                    catred_masked,
                    existing_catred_traces=existing_catred_traces,
                    existing_mosaic_traces=existing_mosaic_traces,
                    existing_mask_overlay_traces=existing_mask_overlay_traces,
                    existing_ned_specz_traces=existing_ned_specz_traces,
                    existing_ned_nearby_catred_traces=existing_ned_nearby_catred_traces,
                    snr_threshold_lower_pzwav=snr_pzwav_lower,
                    snr_threshold_upper_pzwav=snr_pzwav_upper,
                    snr_threshold_lower_amico=snr_amico_lower,
                    snr_threshold_upper_amico=snr_amico_upper,
                    snr_include_missing_pzwav=snr_include_missing_pzwav,
                    snr_include_missing_amico=snr_include_missing_amico,
                    z_threshold_lower=z_lower,
                    z_threshold_upper=z_upper,
                    z_include_missing=redshift_include_missing,
                    richness_threshold_lower=richness_lower,
                    richness_threshold_upper=richness_upper,
                    richness_mode=richness_mode,
                    richness_include_missing=richness_include_missing,
                    flag_quality_zp=flag_quality_zp,
                    flag_quality_rs=flag_quality_rs,
                    idcluster_list=idcluster_list,
                    ned_specz_filter=ned_specz_filter,
                    threshold=threshold,
                    maglim=maglim,
                    show_unmerged_clusters=show_unmerged_clusters,
                    matching_clusters=matching_clusters,
                    show_cltile_info=show_cltile_info,
                    view_bounds=view_bounds,
                )

                # Create figure
                fig = (
                    self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio)
                    if self.figure_manager
                    else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                )

                # Re-inject mosaic layout.images from previous figure
                if current_figure and isinstance(current_figure, dict):
                    prev_images = current_figure.get("layout", {}).get("images") or []
                    mosaic_images = [
                        img for img in prev_images
                        if isinstance(img, dict) and img.get("name", "").startswith("Mosaic")
                    ]
                    if mosaic_images:
                        existing_layout_images = list(fig.layout.images or [])
                        fig.update_layout(images=existing_layout_images + mosaic_images)

                # Preserve zoom state from current figure or relayoutData
                if self.figure_manager:
                    self.figure_manager.preserve_zoom_state(fig, relayout_data, current_figure)
                else:
                    self._preserve_zoom_state_fallback(fig, relayout_data, current_figure)

                # Calculate filtered cluster counts for status (use appropriate SNR values for display)
                if algorithm == "BOTH":
                    filtered_merged_count = self._calculate_filtered_count_both(
                        data["data_detcluster_mergedcat"],
                        snr_pzwav_lower,
                        snr_pzwav_upper,
                        snr_amico_lower,
                        snr_amico_upper,
                        z_lower,
                        z_upper,
                        snr_include_missing_pzwav=snr_include_missing_pzwav,
                        snr_include_missing_amico=snr_include_missing_amico,
                        z_include_missing=redshift_include_missing,
                    )
                    # For status display in BOTH mode, show both SNR ranges
                    snr_lower_display = (
                        f"PZWAV: {snr_pzwav_lower:.2f}, AMICO: {snr_amico_lower:.2f}"
                        if snr_pzwav_lower is not None and snr_amico_lower is not None
                        else None
                    )
                    snr_upper_display = (
                        f"PZWAV: {snr_pzwav_upper:.2f}, AMICO: {snr_amico_upper:.2f}"
                        if snr_pzwav_upper is not None and snr_amico_upper is not None
                        else None
                    )
                elif algorithm == "PZWAV":
                    filtered_merged_count = self._calculate_filtered_count(
                        data["data_detcluster_mergedcat"],
                        snr_pzwav_lower,
                        snr_pzwav_upper,
                        z_lower,
                        z_upper,
                        snr_include_missing=snr_include_missing_pzwav,
                        z_include_missing=redshift_include_missing,
                    )
                    snr_lower_display = snr_pzwav_lower
                    snr_upper_display = snr_pzwav_upper
                else:  # AMICO
                    filtered_merged_count = self._calculate_filtered_count(
                        data["data_detcluster_mergedcat"],
                        snr_amico_lower,
                        snr_amico_upper,
                        z_lower,
                        z_upper,
                        snr_include_missing=snr_include_missing_amico,
                        z_include_missing=redshift_include_missing,
                    )
                    snr_lower_display = snr_amico_lower
                    snr_upper_display = snr_amico_upper

                # Create status info
                status = self._create_status_info(
                    algorithm,
                    data,
                    filtered_merged_count,
                    snr_lower_display,
                    snr_upper_display,
                    z_lower,
                    z_upper,
                    show_polygons,
                    show_mer_tiles,
                    free_aspect_ratio,
                    "info",
                    is_update=True,
                )

                # Create empty PHZ_PDF plot
                empty_phz_fig = self._create_empty_phz_plot()

                if box_coords:
                    fig.add_trace(go.Scatter(
                        x=[box_coords["ra"]],
                        y=[box_coords["dec"]],
                        mode="markers",
                        marker=dict(symbol="square-open", size=18, color="yellow", line=dict(color="yellow", width=2)),
                        name="__selected_cluster__",
                        showlegend=False,
                        hoverinfo="skip",
                    ))

                self._log_figure_size(fig, data)

                # Options change: same catalog, so no rendered_at (the view stays where it is)
                return fig, empty_phz_fig, status, {
                    "algorithm": algorithm, "cull": cull,
                    "span": catalog_span_deg(data),
                }

            except Exception as e:
                error_status = dbc.Alert(f"Error updating: {str(e)}", color="warning")
                return dash.no_update, dash.no_update, error_status, dash.no_update

    def _setup_threshold_clientside_callback(self):
        """Setup client-side callback for real-time threshold filtering of CATRED data"""
        self.app.clientside_callback(
            """
            function(threshold, figure) {
                // If no figure or threshold is null, return the figure as is
                if (!figure || threshold === null || threshold === undefined) {
                    return window.dash_clientside.no_update;
                }
                
                // If figure has no data, return as is
                if (!figure.data || figure.data.length === 0) {
                    return window.dash_clientside.no_update;
                }
                
                // Check if any CATRED traces exist
                let hasCATREDTraces = false;
                for (let i = 0; i < figure.data.length; i++) {
                    if (figure.data[i].name && figure.data[i].name.includes('CATRED')) {
                        hasCATREDTraces = true;
                        break;
                    }
                }
                
                // If no CATRED traces, don't update
                if (!hasCATREDTraces) {
                    return window.dash_clientside.no_update;
                }
                
                // Clone the figure to avoid mutating the original
                let newFigure = JSON.parse(JSON.stringify(figure));
                
                // Filter CATRED traces based on threshold
                for (let i = 0; i < newFigure.data.length; i++) {
                    let trace = newFigure.data[i];
                    
                    // Check if this is a CATRED trace (has effective coverage data)
                    if (trace.name && trace.name.includes('CATRED') && 
                        trace.customdata && trace.customdata.length > 0) {
                        
                        // Store original data if not already stored
                        if (!trace._originalData) {
                            trace._originalData = {
                                x: [...trace.x],
                                y: [...trace.y],
                                text: trace.text ? [...trace.text] : [],
                                customdata: [...trace.customdata]
                            };
                        }
                        
                        // Always filter from original data, not current filtered data
                        let originalData = trace._originalData;
                        let filteredX = [];
                        let filteredY = [];
                        let filteredText = [];
                        let filteredCustomdata = [];
                        
                        for (let j = 0; j < originalData.x.length; j++) {
                            let effectiveCoverage = originalData.customdata[j];
                            
                            // Include point if effective coverage >= threshold
                            if (effectiveCoverage !== null && effectiveCoverage !== undefined && 
                                effectiveCoverage >= threshold) {
                                filteredX.push(originalData.x[j]);
                                filteredY.push(originalData.y[j]);
                                if (originalData.text && originalData.text[j]) {
                                    filteredText.push(originalData.text[j]);
                                }
                                filteredCustomdata.push(effectiveCoverage);
                            }
                        }
                        
                        // Update trace data with filtered results
                        newFigure.data[i].x = filteredX;
                        newFigure.data[i].y = filteredY;
                        if (originalData.text && originalData.text.length > 0) {
                            newFigure.data[i].text = filteredText;
                        }
                        newFigure.data[i].customdata = filteredCustomdata;
                        
                        // Preserve original data for next filtering operation
                        newFigure.data[i]._originalData = originalData;
                        
                        // Update trace name to show filtered count
                        let originalName = trace.name.split(' (')[0]; // Remove existing count
                        newFigure.data[i].name = originalName + ` (${filteredX.length} points, threshold=${threshold})`;
                    }
                }
                
                return newFigure;
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            [Input("catred-threshold-slider", "value")],
            [State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )

    def _setup_snr_pzwav_clientside_callback(self):
        """Setup client-side SNR filtering callback for PZWAV data only (DET_CODE_NB == 2)"""
        self.app.clientside_callback(
            """
            function(snrRange, figure) {
                if (!figure || !figure.data || !snrRange || snrRange.length !== 2) {
                    return figure;
                }
                
                let snrLower = snrRange[0];
                let snrUpper = snrRange[1];
                let newFigure = JSON.parse(JSON.stringify(figure));
                
                for (let i = 0; i < newFigure.data.length; i++) {
                    let trace = newFigure.data[i];
                    
                    // Only filter cluster traces with actual cluster data (have customdata with SNR/Z/DET_CODE)
                    // Skip polygon traces like "Tile X LEV1", "Tile X CORE", "MerTile X"
                    if (trace.name && (trace.name.includes('Merged') || 
                        (trace.name.includes('Tile') && !trace.name.includes('LEV1') && 
                         !trace.name.includes('CORE') && !trace.name.includes('MerTile'))) &&
                        trace.customdata && trace.customdata.length > 0) {
                        
                        // Store original data if not already stored
                        if (!trace._originalClusterData) {
                            trace._originalClusterData = {
                                x: [...trace.x],
                                y: [...trace.y],
                                text: trace.text ? [...trace.text] : [],
                                customdata: trace.customdata ? [...trace.customdata] : []
                            };
                        }
                        
                        // Always filter from original data
                        let originalData = trace._originalClusterData;
                        let filteredX = [];
                        let filteredY = [];
                        let filteredText = [];
                        let filteredCustomdata = [];
                        
                        // Get current redshift filter from trace if it exists
                        let currentZRange = trace._currentZRange || [0, 999]; // Default wide range
                        
                        for (let j = 0; j < originalData.x.length; j++) {
                            // Get SNR, redshift, and algorithm type (DET_CODE_NB) values
                            let snrValue = originalData.customdata[j] ? originalData.customdata[j][0] : null;
                            let zValue = originalData.customdata[j] ? originalData.customdata[j][1] : null;
                            let detCode = originalData.customdata[j] ? originalData.customdata[j][2] : null;
                            
                            // Only filter PZWAV clusters (DET_CODE_NB == 2)
                            // For other algorithms, keep the cluster unchanged
                            let passesSnrFilter = true;
                            if (detCode === 2) {
                                // This is a PZWAV cluster - apply PZWAV SNR filter
                                passesSnrFilter = (snrValue !== null && snrValue !== undefined && 
                                                 snrValue >= snrLower && snrValue <= snrUpper);
                            }
                            // For AMICO (detCode === 1) or other, passesSnrFilter stays true
                            
                            let passesZFilter = (zValue !== null && zValue !== undefined &&
                                               zValue >= currentZRange[0] && zValue <= currentZRange[1]);
                            
                            // Include point only if it passes both filters
                            if (passesSnrFilter && passesZFilter) {
                                filteredX.push(originalData.x[j]);
                                filteredY.push(originalData.y[j]);
                                if (originalData.text && originalData.text[j]) {
                                    filteredText.push(originalData.text[j]);
                                }
                                if (originalData.customdata && originalData.customdata[j]) {
                                    filteredCustomdata.push(originalData.customdata[j]);
                                }
                            }
                        }
                        
                        // Update trace data with filtered results
                        newFigure.data[i].x = filteredX;
                        newFigure.data[i].y = filteredY;
                        if (originalData.text && originalData.text.length > 0) {
                            newFigure.data[i].text = filteredText;
                        }
                        if (originalData.customdata && originalData.customdata.length > 0) {
                            newFigure.data[i].customdata = filteredCustomdata;
                        }
                        
                        // Store current SNR range and preserve original data references
                        newFigure.data[i]._currentSnrRange = [snrLower, snrUpper];
                        newFigure.data[i]._originalClusterData = originalData;
                        if (trace._currentZRange) {
                            newFigure.data[i]._currentZRange = trace._currentZRange;
                        }
                    }
                }
                
                return newFigure;
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            [Input("snr-range-slider-pzwav", "value")],
            [State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )

    def _setup_snr_amico_clientside_callback(self):
        """Setup client-side SNR filtering callback for AMICO data only (DET_CODE_NB == 1)"""
        self.app.clientside_callback(
            """
            function(snrRange, figure) {
                if (!figure || !figure.data || !snrRange || snrRange.length !== 2) {
                    return figure;
                }
                
                let snrLower = snrRange[0];
                let snrUpper = snrRange[1];
                let newFigure = JSON.parse(JSON.stringify(figure));
                
                for (let i = 0; i < newFigure.data.length; i++) {
                    let trace = newFigure.data[i];
                    
                    // Only filter cluster traces with actual cluster data (have customdata with SNR/Z/DET_CODE)
                    // Skip polygon traces like "Tile X LEV1", "Tile X CORE", "MerTile X"
                    if (trace.name && (trace.name.includes('Merged') || 
                        (trace.name.includes('Tile') && !trace.name.includes('LEV1') && 
                         !trace.name.includes('CORE') && !trace.name.includes('MerTile'))) &&
                        trace.customdata && trace.customdata.length > 0) {
                        
                        // Store original data if not already stored
                        if (!trace._originalClusterData) {
                            trace._originalClusterData = {
                                x: [...trace.x],
                                y: [...trace.y],
                                text: trace.text ? [...trace.text] : [],
                                customdata: trace.customdata ? [...trace.customdata] : []
                            };
                        }
                        
                        // Always filter from original data
                        let originalData = trace._originalClusterData;
                        let filteredX = [];
                        let filteredY = [];
                        let filteredText = [];
                        let filteredCustomdata = [];
                        
                        // Get current redshift filter from trace if it exists
                        let currentZRange = trace._currentZRange || [0, 999]; // Default wide range
                        
                        for (let j = 0; j < originalData.x.length; j++) {
                            // Get SNR, redshift, and algorithm type (DET_CODE_NB) values
                            let snrValue = originalData.customdata[j] ? originalData.customdata[j][0] : null;
                            let zValue = originalData.customdata[j] ? originalData.customdata[j][1] : null;
                            let detCode = originalData.customdata[j] ? originalData.customdata[j][2] : null;
                            
                            // Only filter AMICO clusters (DET_CODE_NB == 1)
                            // For other algorithms, keep the cluster unchanged
                            let passesSnrFilter = true;
                            if (detCode === 1) {
                                // This is an AMICO cluster - apply AMICO SNR filter
                                passesSnrFilter = (snrValue !== null && snrValue !== undefined && 
                                                 snrValue >= snrLower && snrValue <= snrUpper);
                            }
                            // For PZWAV (detCode === 2) or other, passesSnrFilter stays true
                            
                            let passesZFilter = (zValue !== null && zValue !== undefined &&
                                               zValue >= currentZRange[0] && zValue <= currentZRange[1]);
                            
                            // Include point only if it passes both filters
                            if (passesSnrFilter && passesZFilter) {
                                filteredX.push(originalData.x[j]);
                                filteredY.push(originalData.y[j]);
                                if (originalData.text && originalData.text[j]) {
                                    filteredText.push(originalData.text[j]);
                                }
                                if (originalData.customdata && originalData.customdata[j]) {
                                    filteredCustomdata.push(originalData.customdata[j]);
                                }
                            }
                        }
                        
                        // Update trace data with filtered results
                        newFigure.data[i].x = filteredX;
                        newFigure.data[i].y = filteredY;
                        if (originalData.text && originalData.text.length > 0) {
                            newFigure.data[i].text = filteredText;
                        }
                        if (originalData.customdata && originalData.customdata.length > 0) {
                            newFigure.data[i].customdata = filteredCustomdata;
                        }
                        
                        // Store current SNR range and preserve original data references
                        newFigure.data[i]._currentSnrRange = [snrLower, snrUpper];
                        newFigure.data[i]._originalClusterData = originalData;
                        if (trace._currentZRange) {
                            newFigure.data[i]._currentZRange = trace._currentZRange;
                        }
                    }
                }
                
                return newFigure;
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            [Input("snr-range-slider-amico", "value")],
            [State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )

    def _setup_redshift_clientside_callback(self):
        """Setup client-side redshift filtering callback"""
        self.app.clientside_callback(
            """
            function(redshiftRange, figure) {
                if (!figure || !figure.data || !redshiftRange || redshiftRange.length !== 2) {
                    return figure;
                }
                
                let zLower = redshiftRange[0];
                let zUpper = redshiftRange[1];
                let newFigure = JSON.parse(JSON.stringify(figure));
                
                for (let i = 0; i < newFigure.data.length; i++) {
                    let trace = newFigure.data[i];
                    
                    // Only filter cluster traces with actual cluster data (have customdata with SNR/Z)
                    // Skip polygon traces like "Tile X LEV1", "Tile X CORE", "MerTile X"
                    if (trace.name && (trace.name.includes('Merged') || 
                        (trace.name.includes('Tile') && !trace.name.includes('LEV1') && 
                         !trace.name.includes('CORE') && !trace.name.includes('MerTile'))) &&
                        trace.customdata && trace.customdata.length > 0) {
                        
                        // Store original data if not already stored
                        if (!trace._originalClusterData) {
                            trace._originalClusterData = {
                                x: [...trace.x],
                                y: [...trace.y],
                                text: trace.text ? [...trace.text] : [],
                                customdata: trace.customdata ? [...trace.customdata] : []
                            };
                        }
                        
                        // Always filter from original data
                        let originalData = trace._originalClusterData;
                        let filteredX = [];
                        let filteredY = [];
                        let filteredText = [];
                        let filteredCustomdata = [];
                        
                        // Get current SNR filter from trace if it exists
                        let currentSnrRange = trace._currentSnrRange || [0, 999]; // Default wide range
                        
                        for (let j = 0; j < originalData.x.length; j++) {
                            // Get SNR and redshift values
                            let snrValue = originalData.customdata[j] ? originalData.customdata[j][0] : null;
                            let zValue = originalData.customdata[j] ? originalData.customdata[j][1] : null;
                            
                            // Apply both SNR and redshift filters together
                            let passesSnrFilter = (snrValue !== null && snrValue !== undefined && 
                                                 snrValue >= currentSnrRange[0] && snrValue <= currentSnrRange[1]);
                            let passesZFilter = (zValue !== null && zValue !== undefined &&
                                               zValue >= zLower && zValue <= zUpper);
                            
                            // Include point only if it passes both filters
                            if (passesSnrFilter && passesZFilter) {
                                filteredX.push(originalData.x[j]);
                                filteredY.push(originalData.y[j]);
                                if (originalData.text && originalData.text[j]) {
                                    filteredText.push(originalData.text[j]);
                                }
                                if (originalData.customdata && originalData.customdata[j]) {
                                    filteredCustomdata.push(originalData.customdata[j]);
                                }
                            }
                        }
                        
                        // Update trace data with filtered results
                        newFigure.data[i].x = filteredX;
                        newFigure.data[i].y = filteredY;
                        if (originalData.text && originalData.text.length > 0) {
                            newFigure.data[i].text = filteredText;
                        }
                        if (originalData.customdata && originalData.customdata.length > 0) {
                            newFigure.data[i].customdata = filteredCustomdata;
                        }
                        
                        // Store current redshift range and preserve original data references
                        newFigure.data[i]._currentZRange = [zLower, zUpper];
                        newFigure.data[i]._originalClusterData = originalData;
                        if (trace._currentSnrRange) {
                            newFigure.data[i]._currentSnrRange = trace._currentSnrRange;
                        }
                    }
                }
                
                return newFigure;
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            [Input("redshift-range-slider", "value")],
            [State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )

    def _setup_viewport_zoom_indicator_callback(self):
        """Clientside callback: update viewport zoom indicator from relayoutData."""
        self.app.clientside_callback(
            """
            function(relayoutData) {
                if (!relayoutData) {
                    return ['Zoom in, then press Apply filters', {'color': '#6c757d'}];
                }

                var raRange = null, decRange = null;

                if ('xaxis.range[0]' in relayoutData && 'xaxis.range[1]' in relayoutData) {
                    raRange = Math.abs(relayoutData['xaxis.range[1]'] - relayoutData['xaxis.range[0]']);
                } else if ('xaxis.range' in relayoutData) {
                    raRange = Math.abs(relayoutData['xaxis.range'][1] - relayoutData['xaxis.range'][0]);
                }

                if ('yaxis.range[0]' in relayoutData && 'yaxis.range[1]' in relayoutData) {
                    decRange = Math.abs(relayoutData['yaxis.range[1]'] - relayoutData['yaxis.range[0]']);
                } else if ('yaxis.range' in relayoutData) {
                    decRange = Math.abs(relayoutData['yaxis.range'][1] - relayoutData['yaxis.range'][0]);
                }

                if (raRange === null || decRange === null) {
                    return ['Zoom in, then press Apply filters', {'color': '#6c757d'}];
                }

                var label = raRange.toFixed(1) + '\u00b0 \u00d7 ' + decRange.toFixed(1) + '\u00b0';
                var maxDim = Math.max(raRange, decRange);

                if (maxDim < 5.0) {
                    return ['\u2713 ' + label + ' \u2014 ovals draw on Apply filters', {'color': '#198754'}];
                } else if (maxDim < 15.0) {
                    return ['\u26a0 ' + label + ' \u2014 zoom in for fewer ovals', {'color': '#fd7e14'}];
                } else {
                    return ['\u2715 ' + label + ' \u2014 too wide, zoom in first', {'color': '#dc3545'}];
                }
            }
            """,
            [
                Output("viewport-zoom-indicator", "children"),
                Output("viewport-zoom-indicator", "style"),
            ],
            Input("cluster-plot", "relayoutData"),
            prevent_initial_call=False,
        )

    def load_data(self, algorithm):
        """Load data using modular or fallback method"""
        if self.data_loader:
            return self.data_loader.load_data(algorithm)
        else:
            # Fallback to inline data loading
            return self._load_data_fallback(algorithm)

    def create_traces(
        self,
        data,
        show_polygons,
        show_mer_tiles,
        relayout_data,
        catred_masked,
        existing_catred_traces=None,
        existing_mosaic_traces=None,
        existing_mask_overlay_traces=None,
        existing_ned_specz_traces=None,
        existing_ned_nearby_catred_traces=None,
        manual_catred_data=None,
        snr_threshold_lower_pzwav=None,
        snr_threshold_upper_pzwav=None,
        snr_threshold_lower_amico=None,
        snr_threshold_upper_amico=None,
        snr_include_missing_pzwav=True,
        snr_include_missing_amico=True,
        z_threshold_lower=None,
        z_threshold_upper=None,
        z_include_missing=True,
        richness_threshold_lower=None,
        richness_threshold_upper=None,
        richness_mode=None,
        richness_include_missing=True,
        flag_quality_zp=None,
        flag_quality_rs=None,
        idcluster_list=None,
        ned_specz_filter=False,
        threshold=0.8,
        maglim=None,
        show_unmerged_clusters=False,
        matching_clusters=False,
        show_cltile_info=True,
        view_bounds=None,
    ):
        """Create traces using modular or fallback method"""
        if self.trace_creator:
            return self.trace_creator.create_traces(
                data,
                show_polygons,
                show_mer_tiles,
                relayout_data,
                catred_masked,
                existing_catred_traces=existing_catred_traces,
                existing_mosaic_traces=existing_mosaic_traces,
                existing_mask_overlay_traces=existing_mask_overlay_traces,
                existing_ned_specz_traces=existing_ned_specz_traces,
                existing_ned_nearby_catred_traces=existing_ned_nearby_catred_traces,
                manual_catred_data=manual_catred_data,
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
                threshold=threshold,
                maglim=maglim,
                show_unmerged_clusters=show_unmerged_clusters,
                matching_clusters=matching_clusters,
                show_cltile_info=show_cltile_info,
                view_bounds=view_bounds,
            )
        else:
            # Fallback to inline trace creation
            return self._create_traces_fallback(
                data,
                show_polygons,
                show_mer_tiles,
                relayout_data,
                catred_masked,
                existing_catred_traces=existing_catred_traces,
                existing_mosaic_traces=existing_mosaic_traces,
                existing_mask_overlay_traces=existing_mask_overlay_traces,
                manual_catred_data=manual_catred_data,
                snr_threshold_lower_pzwav=snr_threshold_lower_pzwav,
                snr_threshold_upper_pzwav=snr_threshold_upper_pzwav,
                snr_threshold_lower_amico=snr_threshold_lower_amico,
                snr_threshold_upper_amico=snr_threshold_upper_amico,
                z_threshold_lower=z_threshold_lower,
                z_threshold_upper=z_threshold_upper,
                idcluster_list=idcluster_list,
                threshold=threshold,
                show_unmerged_clusters=show_unmerged_clusters,
                matching_clusters=matching_clusters,
                show_cltile_info=show_cltile_info,
            )

    # Helper methods for fallback and utility functions
    def _create_initial_empty_plots(self, free_aspect_ratio):
        """Create initial empty plots"""
        # Initial empty figure
        initial_fig = go.Figure()

        # Configure aspect ratio based on setting
        if free_aspect_ratio:
            xaxis_config = dict(visible=False, autorange="reversed")
            yaxis_config = dict(visible=False)
        else:
            xaxis_config = dict(
                scaleanchor="y",
                scaleratio=1,
                constrain="domain",
                visible=False,
                autorange="reversed",
            )
            yaxis_config = dict(constrain="domain", visible=False)  # type: ignore

        initial_fig.update_layout(
            title="",
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis=xaxis_config,
            yaxis=yaxis_config,
            autosize=True,
            showlegend=False,
            annotations=[
                dict(
                    text="Select your preferred algorithm and display options from the sidebar,<br>then click 'Render clusters' to generate the plot.",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    xanchor="center",
                    yanchor="middle",
                    showarrow=False,
                    font=dict(size=16, color="gray"),
                )
            ],
        )

        # Initial empty PHZ_PDF plot
        initial_phz_fig = self._create_empty_phz_plot(
            "Click a CATRED source on the map to see its redshift probability, p(z)"
        )

        initial_status = dbc.Alert(
            [
                html.H6("Ready to render", className="mb-1"),
                html.P(
                    "Click 'Render clusters' to begin. Display options then update live and keep your zoom; filters take effect when you press Apply filters.",
                    className="mb-0",
                ),
            ],
            color="secondary",
            className="mt-2",
        )

        return initial_fig, initial_phz_fig, initial_status

    def _create_empty_phz_plot(self, message="Click a CATRED source on the map to see its redshift probability, p(z)"):
        """Empty p(z) panel: a centred hint, no axes or grid"""
        empty_phz_fig = go.Figure()
        empty_phz_fig.update_layout(
            template="plotly_white",
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            margin=dict(l=16, r=16, t=16, b=16),
            showlegend=False,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[
                dict(
                    text=message,
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    xanchor="center",
                    yanchor="middle",
                    showarrow=False,
                    font=dict(size=13, color="#59616b"),
                )
            ],
        )
        return empty_phz_fig

    def _create_error_plots(self, error_message):
        """Create error plots for exception handling"""
        error_fig = go.Figure()
        error_fig.add_annotation(
            text=f"Error loading data: {error_message}",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=dict(size=16, color="red"),
        )
        error_fig.update_layout(
            title="Error Loading Visualization", margin=dict(l=40, r=120, t=60, b=40), autosize=True
        )

        error_status = dbc.Alert(f"Error: {error_message}", color="danger")
        error_phz_fig = self._create_empty_phz_plot("Error loading data")

        return error_fig, error_phz_fig, error_status


    def _calculate_filtered_count(
        self,
        cluster_data,
        snr_lower,
        snr_upper,
        z_lower,
        z_upper,
        snr_include_missing=True,
        z_include_missing=True,
    ):
        """Calculate filtered cluster count based on SNR and redshift range"""
        cluster_data_1 = cluster_data
        if snr_lower is not None or snr_upper is not None:
            snr_col = cluster_data["SNR_CLUSTER"]
            if snr_lower is not None and snr_upper is not None:
                snr_mask = (snr_col >= snr_lower) & (snr_col <= snr_upper)
            elif snr_upper is not None:
                snr_mask = snr_col <= snr_upper
            else:
                snr_mask = snr_col >= snr_lower
            if snr_include_missing:
                snr_mask = snr_mask | np.isnan(snr_col)
            cluster_data_1 = cluster_data[snr_mask]

        if z_lower is None and z_upper is None:
            return len(cluster_data_1)

        z_col = cluster_data_1["Z_CLUSTER"]
        if z_lower is not None and z_upper is not None:
            z_mask = (z_col >= z_lower) & (z_col <= z_upper)
        elif z_upper is not None:
            z_mask = z_col <= z_upper
        else:
            z_mask = z_col >= z_lower
        if z_include_missing:
            z_mask = z_mask | np.isnan(z_col)

        return len(cluster_data_1[z_mask])

    def _calculate_filtered_count_both(
        self,
        cluster_data,
        snr_pzwav_lower,
        snr_pzwav_upper,
        snr_amico_lower,
        snr_amico_upper,
        z_lower,
        z_upper,
        snr_include_missing_pzwav=True,
        snr_include_missing_amico=True,
        z_include_missing=True,
    ):
        """Calculate filtered cluster count for BOTH mode with separate SNR ranges"""
        # Filter PZWAV clusters (DET_CODE_NB == 2)
        if "DET_CODE_NB" in cluster_data.dtype.names:
            pzwav_data = cluster_data[cluster_data["DET_CODE_NB"] == 2]
        else:
            pzwav_data = cluster_data
        if snr_pzwav_lower is not None and snr_pzwav_upper is not None:
            pzwav_snr = pzwav_data["SNR_CLUSTER"]
            pzwav_mask = (pzwav_snr >= snr_pzwav_lower) & (pzwav_snr <= snr_pzwav_upper)
            if snr_include_missing_pzwav:
                pzwav_mask = pzwav_mask | np.isnan(pzwav_snr)
            pzwav_data = pzwav_data[pzwav_mask]

        # Filter AMICO clusters (DET_CODE_NB == 1)
        if "DET_CODE_NB" in cluster_data.dtype.names:
            amico_data = cluster_data[cluster_data["DET_CODE_NB"] == 1]
        else:
            amico_data = cluster_data[:0]  # empty — avoid double-counting when column absent
        if snr_amico_lower is not None and snr_amico_upper is not None:
            amico_snr = amico_data["SNR_CLUSTER"]
            amico_mask = (amico_snr >= snr_amico_lower) & (amico_snr <= snr_amico_upper)
            if snr_include_missing_amico:
                amico_mask = amico_mask | np.isnan(amico_snr)
            amico_data = amico_data[amico_mask]

        # Combine filtered data
        combined_data = np.concatenate([pzwav_data, amico_data])

        # Apply redshift filter
        if z_lower is not None or z_upper is not None:
            z_col = combined_data["Z_CLUSTER"]
            if z_lower is not None and z_upper is not None:
                z_mask = (z_col >= z_lower) & (z_col <= z_upper)
            elif z_lower is not None:
                z_mask = z_col >= z_lower
            else:
                z_mask = z_col <= z_upper
            if z_include_missing:
                z_mask = z_mask | np.isnan(z_col)
            combined_data = combined_data[z_mask]

        return len(combined_data)

    def _get_idclusters_array(
            self, 
            upload_contents, 
            upload_filename
        ) -> Optional[NDArray[np.int64]]:
        """Extract cluster IDs from uploaded txt/dat/csv contents."""
        if not upload_contents or not upload_filename:
            return None

        try:
            _, content_string = upload_contents.split(",", 1)
            decoded_text = base64.b64decode(content_string).decode("utf-8", errors="ignore")
            suffix = upload_filename.lower().rsplit(".", 1)[-1]

            if suffix in ("txt", "dat"):
                values = [
                    int(line.strip())
                    for line in decoded_text.splitlines()
                    if line.strip()
                ]
                return np.asarray(values, dtype=int)

            if suffix == "csv":
                df = pd.read_csv(io.StringIO(decoded_text))

                preferred_columns = ["ID_UNIQUE_CLUSTER", "idclusters", "ID", "id"]
                for col in preferred_columns:
                    if col in df.columns:
                        series = pd.to_numeric(df[col], errors="coerce").dropna()
                        arr = series.to_numpy(dtype=np.int64)
                        return cast(NDArray[np.int64], arr)

                numeric_df = df.apply(pd.to_numeric, errors="coerce")
                numeric_cols = numeric_df.columns[numeric_df.notna().any()].tolist()

                if len(numeric_cols) == 1:
                    arr = numeric_df[numeric_cols[0]].dropna().to_numpy(dtype=np.int64)
                    return cast(NDArray[np.int64], arr)
                
                if len(numeric_cols) > 1:
                    values = numeric_df[numeric_cols].to_numpy().ravel()
                    values = values[~pd.isna(values)]
                    return np.asarray(values, dtype=np.int64)

                raise ValueError("No numeric ID column found in CSV.")

            raise ValueError(f"Unsupported file type: {upload_filename}")

        except Exception as e:
            print(f"Error processing uploaded file: {e}")
            return None

    def _create_status_info(
        self,
        algorithm,
        data,
        filtered_merged_count,
        snr_lower,
        snr_upper,
        z_lower,
        z_upper,
        show_polygons,
        show_mer_tiles,
        free_aspect_ratio,
        alert_color,
        is_update=False,
    ):
        """Create status information display

        Note: snr_lower and snr_upper can be either single float values or formatted strings
        (e.g., "PZWAV: 4.50, AMICO: 3.20") for BOTH mode.
        """
        # Status info
        mer_status = ""
        if show_mer_tiles and not show_polygons:
            mer_status = " | MER tiles: ON"
        elif show_mer_tiles and show_polygons:
            mer_status = " | MER tiles: OFF (fill mode)"
        else:
            mer_status = " | MER tiles: OFF"

        aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"

        # Format SNR filter status
        snr_filter_text = "No SNR filtering"

        # Check if snr_lower/snr_upper are already formatted strings (for BOTH mode)
        if isinstance(snr_lower, str) or isinstance(snr_upper, str):
            # Already formatted for BOTH mode
            if snr_lower is not None and snr_upper is not None:
                snr_filter_text = f"{snr_lower} ≤ SNR ≤ {snr_upper}"
            elif snr_lower is not None:
                snr_filter_text = f"SNR ≥ {snr_lower}"
            elif snr_upper is not None:
                snr_filter_text = f"SNR ≤ {snr_upper}"
        elif snr_lower is not None and snr_upper is not None:
            snr_filter_text = f"{snr_lower:.3f} ≤ SNR ≤ {snr_upper:.3f}"
        elif snr_lower is not None:
            snr_filter_text = f"SNR ≥ {snr_lower:.3f}"
        elif snr_upper is not None:
            snr_filter_text = f"SNR ≤ {snr_upper:.3f}"

        # Format Redshift filter status
        z_filter_text = "No z filtering"
        if z_lower is not None and z_upper is not None:
            z_filter_text = f"{z_lower:.3f} ≤ z ≤ {z_upper:.3f}"
        elif z_lower is not None:
            z_filter_text = f"z ≥ {z_lower:.3f}"
        elif z_upper is not None:
            z_filter_text = f"z ≤ {z_upper:.3f}"

        timestamp_text = "Updated at" if is_update else "Rendered at"

        status = dbc.Alert(
            [
                html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                html.P(
                    f"Merged clusters: {filtered_merged_count}/{len(data['data_detcluster_mergedcat'])} (filtered)",
                    className="mb-1",
                ),
                html.P(
                    f"Individual tiles: {len(data['data_detcluster_by_cltile'])}", className="mb-1"
                ),
                html.P(f"SNR Filter: {snr_filter_text}", className="mb-1"),
                html.P(f"Redshift Filter: {z_filter_text}", className="mb-1"),
                html.P(
                    f"Polygon mode: {'Filled' if show_polygons else 'Outline'}{mer_status}",
                    className="mb-1",
                ),
                html.P(f"Aspect ratio: {aspect_mode}", className="mb-1"),
                html.Small(
                    f"{timestamp_text}: {pd.Timestamp.now().strftime('%H:%M:%S')}",
                    className="text-muted",
                ),
            ],
            color=alert_color,
            className="mt-2",
        )

        return status

    # Fallback methods for backward compatibility
    def _load_data_fallback(self, algorithm):
        """Fallback data loading method"""
        # This would contain the original inline data loading logic
        # For now, return empty structure to prevent errors
        return {
            "data_detcluster_mergedcat": pd.DataFrame(),
            "data_detcluster_by_cltile": pd.DataFrame(),
            "snr_min": 0,
            "snr_max": 100,
            "z_min": 0,
            "z_max": 10,
        }

    def _create_traces_fallback(
        self,
        data,
        show_polygons,
        show_mer_tiles,
        relayout_data,
        catred_masked,
        existing_catred_traces=None,
        existing_mosaic_traces=None,
        existing_mask_overlay_traces=None,
        manual_catred_data=None,
        snr_threshold_lower_pzwav=None,
        snr_threshold_upper_pzwav=None,
        snr_threshold_lower_amico=None,
        snr_threshold_upper_amico=None,
        z_threshold_lower=None,
        z_threshold_upper=None,
        idcluster_list=None,
        threshold=0.8,
        show_unmerged_clusters=False,
        show_cltile_info=True,
        matching_clusters=False,
    ):
        """Fallback trace creation method"""
        # This would contain the original inline trace creation logic
        # For now, return empty traces to prevent errors
        return []

    def _create_fallback_figure(self, traces, algorithm, free_aspect_ratio):
        """Fallback figure creation method"""
        fig = go.Figure(traces)

        xaxis_config, yaxis_config = self.figure_manager._get_axis_config(
            free_aspect_ratio,
            dec_center=self.figure_manager._extract_dec_center(traces),
        )

        fig.update_layout(
            title=f"Cluster Detection Visualization - {algorithm}",
            xaxis_title="Right Ascension (degrees)",
            yaxis_title="Declination (degrees)",
            legend=dict(
                title="Legend",
                orientation="v",
                xanchor="left",
                x=1.01,
                yanchor="top",
                y=1,
                font=dict(size=10),
            ),
            hovermode="closest",
            margin=dict(l=40, r=120, t=60, b=40),
            xaxis=xaxis_config,
            yaxis=yaxis_config,
            autosize=True,
        )

        return fig

    def _preserve_zoom_state_fallback(self, fig, relayout_data, current_figure=None):
        """Fallback zoom state preservation method"""
        # Preserve zoom state if available
        if relayout_data and any(
            key in relayout_data
            for key in ["xaxis.range[0]", "xaxis.range[1]", "yaxis.range[0]", "yaxis.range[1]"]
        ):
            if "xaxis.range[0]" in relayout_data and "xaxis.range[1]" in relayout_data:
                fig.update_xaxes(
                    range=[relayout_data["xaxis.range[0]"], relayout_data["xaxis.range[1]"]],
                    autorange=False,
                )
            if "yaxis.range[0]" in relayout_data and "yaxis.range[1]" in relayout_data:
                fig.update_yaxes(
                    range=[relayout_data["yaxis.range[0]"], relayout_data["yaxis.range[1]"]]
                )
        elif relayout_data and "xaxis.range" in relayout_data:
            fig.update_xaxes(range=relayout_data["xaxis.range"], autorange=False)
            if "yaxis.range" in relayout_data:
                fig.update_yaxes(range=relayout_data["yaxis.range"])
        elif current_figure and "layout" in current_figure:
            # Fallback: try to preserve from current figure layout
            current_layout = current_figure["layout"]
            if "xaxis" in current_layout and "range" in current_layout["xaxis"]:
                fig.update_xaxes(range=current_layout["xaxis"]["range"], autorange=False)
            if "yaxis" in current_layout and "range" in current_layout["yaxis"]:
                fig.update_yaxes(range=current_layout["yaxis"]["range"])
