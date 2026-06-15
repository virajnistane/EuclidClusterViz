"""
Main plot callbacks for cluster visualization.

Handles primary rendering logic for the main cluster visualization plot,
including initial rendering, real-time option updates, and SNR filtering.
"""

import base64
import io
from typing import Optional, cast
from numpy.typing import NDArray

import dash  # type: ignore[import]
import dash_bootstrap_components as dbc  # type: ignore[import]
import numpy as np
import pandas as pd  # type: ignore[import]
import plotly.graph_objs as go  # type: ignore[import]
from dash import Input, Output, State, html

try:
    from cluster_visualization.callbacks.utils import get_idclusters_array
except ImportError:
    print("Warning: Could not import get_idclusters_array from utils. ID cluster upload functionality may be affected.")


def _build_selection_shape(box_coords: dict, relayout_data: Optional[dict]) -> dict:
    """Build a rectangle shape dict for the selected cluster point."""
    ra, dec = box_coords["ra"], box_coords["dec"]
    half_w, half_h = 0.3, 0.3
    if relayout_data:
        x0 = relayout_data.get("xaxis.range[0]")
        x1 = relayout_data.get("xaxis.range[1]")
        y0 = relayout_data.get("yaxis.range[0]")
        y1 = relayout_data.get("yaxis.range[1]")
        if x0 is not None and x1 is not None:
            half_w = abs(x1 - x0) * 0.015
        if y0 is not None and y1 is not None:
            half_h = abs(y1 - y0) * 0.015
    return dict(
        type="rect", xref="x", yref="y",
        x0=ra - half_w, x1=ra + half_w,
        y0=dec - half_h, y1=dec + half_h,
        line=dict(color="yellow", width=2),
        fillcolor="rgba(0,0,0,0)",
        layer="above",
    )


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
                Output("snr-range-display-pzwav", "children"),
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

                display_text = html.Div(
                    [
                        html.Small(
                            f"SNR Range: {snr_min:.2f} to {snr_max:.2f}", className="text-muted"
                        ),
                        html.Small(" | Move sliders to set filter range", className="text-muted"),
                    ]
                )

                return snr_min, snr_max, default_value, marks, display_text

            except Exception as e:
                # Fallback values if data loading fails
                return (
                    0,
                    100,
                    [0, 100],
                    {0: "0", 100: "100"},
                    html.Small("SNR data not available", className="text-muted"),
                )

    def _setup_snr_slider_amico_callback(self):
        """Setup SNR slider initialization callback"""

        @self.app.callback(
            [
                Output("snr-range-slider-amico", "min"),
                Output("snr-range-slider-amico", "max"),
                Output("snr-range-slider-amico", "value"),
                Output("snr-range-slider-amico", "marks"),
                Output("snr-range-display-amico", "children"),
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

                display_text = html.Div(
                    [
                        html.Small(
                            f"SNR Range: {snr_min:.2f} to {snr_max:.2f}", className="text-muted"
                        ),
                        html.Small(" | Move sliders to set filter range", className="text-muted"),
                    ]
                )

                return snr_min, snr_max, default_value, marks, display_text

            except Exception as e:
                # Fallback values if data loading fails
                return (
                    0,
                    100,
                    [0, 100],
                    {0: "0", 100: "100"},
                    html.Small("SNR data not available", className="text-muted"),
                )

    def _setup_redshift_slider_callback(self):
        """Setup redshift slider initialization callback"""

        @self.app.callback(
            [
                Output("redshift-range-slider", "min"),
                Output("redshift-range-slider", "max"),
                Output("redshift-range-slider", "value"),
                Output("redshift-range-slider", "marks"),
                Output("redshift-range-display", "children"),
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

                display_text = html.Div(
                    [
                        html.Small(
                            f"Redshift Range: {z_min:.2f} to {z_max:.2f}", className="text-muted"
                        ),
                        html.Small(" | Move sliders to set filter range", className="text-muted"),
                    ]
                )

                return z_min, z_max, default_value, marks, display_text

            except Exception as e:
                # Fallback values if data loading fails
                return (
                    0,
                    10,
                    [0, 10],
                    {0: "0", 10: "10"},
                    html.Small("Redshift data not available", className="text-muted"),
                )

    def _setup_richness_slider_zp_callback(self):
        @self.app.callback(
            [
                Output("richness-range-slider-zp", "min"),
                Output("richness-range-slider-zp", "max"),
                Output("richness-range-slider-zp", "value"),
                Output("richness-range-slider-zp", "marks"),
                Output("richness-range-display-zp", "children"),
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
                marks = {r_min: f"{r_min:.1f}", r_max: f"{r_max:.1f}"}
                display_text = html.Div(
                    [
                        html.Small(f"ZP Range: {r_min:.2f} to {r_max:.2f}", className="text-muted"),
                        html.Small(" | Move sliders to set filter range", className="text-muted"),
                    ]
                )
                return r_min, r_max, [r_min, r_max], marks, display_text
            except Exception:
                return (
                    0, 100, [0, 100], {0: "0", 100: "100"},
                    html.Small("Richness ZP data not available", className="text-muted"),
                )

    def _setup_richness_slider_rs_callback(self):
        @self.app.callback(
            [
                Output("richness-range-slider-rs", "min"),
                Output("richness-range-slider-rs", "max"),
                Output("richness-range-slider-rs", "value"),
                Output("richness-range-slider-rs", "marks"),
                Output("richness-range-display-rs", "children"),
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
                marks = {r_min: f"{r_min:.1f}", r_max: f"{r_max:.1f}"}
                display_text = html.Div(
                    [
                        html.Small(f"RS Range: {r_min:.2f} to {r_max:.2f}", className="text-muted"),
                        html.Small(" | Move sliders to set filter range", className="text-muted"),
                    ]
                )
                return r_min, r_max, [r_min, r_max], marks, display_text
            except Exception:
                return (
                    0, 100, [0, 100], {0: "0", 100: "100"},
                    html.Small("Richness RS data not available", className="text-muted"),
                )

    def _setup_main_render_callback(self):
        """Setup main rendering callback for initial plot and SNR/redshift filtering"""

        @self.app.callback(
            [
                Output("cluster-plot", "figure"),
                Output("phz-pdf-plot", "figure"),
                Output("status-info", "children"),
            ],
            [
                Input("render-button", "n_clicks"),
                Input("snr-render-button-pzwav", "n_clicks"),
                Input("snr-render-button-amico", "n_clicks"),
                Input("redshift-render-button", "n_clicks"),
                Input("richness-render-button-zp", "n_clicks"),
                Input("richness-render-button-rs", "n_clicks"),
                Input("idcluster-render-button", "n_clicks"),
                Input("rerender-ovals-button", "n_clicks"),
            ],
            [
                State("algorithm-dropdown", "value"),
                State("matching-clusters-switch", "value"),
                State("snr-range-slider-pzwav", "value"),
                State("snr-range-slider-amico", "value"),
                State("redshift-range-slider", "value"),
                State("richness-range-slider-zp", "value"),
                State("richness-range-slider-rs", "value"),
                State("richness-mode-radio", "value"),
                State("flag-quality-zp-checklist", "value"),
                State("flag-quality-rs-checklist", "value"),
                State("idcluster-upload", "contents"),
                State("idcluster-upload", "filename"),
                State("polygon-switch", "value"),
                State("mer-switch", "value"),
                State("aspect-ratio-switch", "value"),
                State("unmerged-clusters-switch", "value"),
                State("cltile-info-switch", "value"),
                State("catred-mode-switch", "value"),
                State("catred-threshold-slider", "value"),
                State("magnitude-limit-slider", "value"),
                State("cluster-plot", "relayoutData"),
                State("selected-cluster-box-coords", "data"),
            ],
            background=True,
            running=[
                (Output("data-load-progress-container", "style"), {"display": "block"}, {"display": "none"}),
                (Output("render-button", "disabled"), True, False),
                (Output("snr-render-button-pzwav", "disabled"), True, False),
                (Output("snr-render-button-amico", "disabled"), True, False),
                (Output("redshift-render-button", "disabled"), True, False),
                (Output("richness-render-button-zp", "disabled"), True, False),
                (Output("richness-render-button-rs", "disabled"), True, False),
                (Output("idcluster-render-button", "disabled"), True, False),
            ],
            progress=[
                Output("data-load-progress", "value"),
                Output("data-load-label", "children"),
            ],
        )
        def update_plot(
            set_progress,
            n_clicks,
            snr_pzwav_n_clicks,
            snr_amico_n_clicks,
            redshift_n_clicks,
            richness_zp_n_clicks,
            richness_rs_n_clicks,
            idcluster_n_clicks,
            rerender_ovals_n_clicks,
            algorithm,
            matching_clusters,
            snr_range_pzwav,
            snr_range_amico,
            redshift_range,
            richness_range_zp,
            richness_range_rs,
            richness_mode,
            flag_quality_zp,
            flag_quality_rs,
            idcluster_upload_contents,
            idcluster_upload_filename,
            show_polygons,
            show_mer_tiles,
            free_aspect_ratio,
            show_unmerged_clusters,
            show_cltile_info,
            catred_masked,
            threshold,
            maglim,
            relayout_data,
            box_coords,
        ):
            # Only render if button has been clicked at least once
            if all(
                clicks in [None, 0]
                for clicks in [
                    n_clicks,
                    snr_pzwav_n_clicks,
                    snr_amico_n_clicks,
                    redshift_n_clicks,
                    richness_zp_n_clicks,
                    richness_rs_n_clicks,
                    idcluster_n_clicks,
                    rerender_ovals_n_clicks,
                ]
            ):
                return self._create_initial_empty_plots(free_aspect_ratio)

            try:
                set_progress((5, f"Preparing {algorithm} data..."))

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

                idcluster_list = None
                if idcluster_upload_contents and idcluster_upload_filename:
                    set_progress((10, f"Processing uploaded cluster IDs from {idcluster_upload_filename}..."))
                    idcluster_list = get_idclusters_array(idcluster_upload_contents, idcluster_upload_filename)

                # Load data for selected algorithm
                set_progress((20, f"Loading {algorithm} catalog..."))
                data = self.load_data(algorithm)

                # Only reset CATRED traces cache if algorithm changed, not for SNR/redshift filtering
                # CATRED data doesn't have SNR and shouldn't be affected by cluster-level filtering
                # Note: This preserves CATRED data when only SNR/redshift filters change

                set_progress((55, "Creating visualization traces..."))
                # Create traces with separate SNR thresholds
                traces = self.create_traces(
                    data,
                    show_polygons,
                    show_mer_tiles,
                    relayout_data,
                    catred_masked,
                    snr_threshold_lower_pzwav=snr_pzwav_lower,
                    snr_threshold_upper_pzwav=snr_pzwav_upper,
                    snr_threshold_lower_amico=snr_amico_lower,
                    snr_threshold_upper_amico=snr_amico_upper,
                    z_threshold_lower=z_lower,
                    z_threshold_upper=z_upper,
                    richness_threshold_lower=richness_lower,
                    richness_threshold_upper=richness_upper,
                    richness_mode=richness_mode,
                    flag_quality_zp=flag_quality_zp,
                    flag_quality_rs=flag_quality_rs,
                    idcluster_list=idcluster_list,
                    threshold=threshold,
                    maglim=maglim,
                    show_unmerged_clusters=show_unmerged_clusters,
                    matching_clusters=matching_clusters,
                    show_cltile_info=show_cltile_info,
                )

                # Create figure
                set_progress((80, "Building figure..."))
                fig = (
                    self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio)
                    if self.figure_manager
                    else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                )

                # Preserve zoom state if available
                if self.figure_manager:
                    self.figure_manager.preserve_zoom_state(fig, relayout_data)
                else:
                    self._preserve_zoom_state_fallback(fig, relayout_data)

                # Calculate filtered cluster counts for status (use appropriate SNR values for display)
                if algorithm == "BOTH":
                    # For BOTH mode, we'll show combined count
                    filtered_merged_count = self._calculate_filtered_count_both(
                        data["data_detcluster_mergedcat"],
                        snr_pzwav_lower,
                        snr_pzwav_upper,
                        snr_amico_lower,
                        snr_amico_upper,
                        z_lower,
                        z_upper,
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
                    "success",
                )

                # Create empty PHZ_PDF plot
                empty_phz_fig = self._create_empty_phz_plot()
                
                if box_coords:
                    fig.update_layout(shapes=[_build_selection_shape(box_coords, relayout_data)])

                _fig_json = fig.to_json()
                print(f"Debug: Figure JSON {len(_fig_json) / 1024:.0f} KB, {len(traces)} traces, {len(data['data_detcluster_mergedcat'])} merged clusters")

                return fig, empty_phz_fig, status

            except Exception as e:
                return self._create_error_plots(str(e))

    def _setup_options_update_callback(self):
        """Setup real-time options update callback (preserves zoom)"""

        @self.app.callback(
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("phz-pdf-plot", "figure", allow_duplicate=True),
                Output("status-info", "children", allow_duplicate=True),
            ],
            [
                Input("algorithm-dropdown", "value"),
                Input("polygon-switch", "value"),
                Input("mer-switch", "value"),
                Input("aspect-ratio-switch", "value"),
                Input("unmerged-clusters-switch", "value"),
                Input("cltile-info-switch", "value"),
                Input("catred-mode-switch", "value"),
                Input("richness-mode-radio", "value"),
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
            richness_mode,
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
        ):
            # Only update if render button has been clicked at least once
            if n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update

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

                # Process uploaded ID cluster list if provided
                if idcluster_upload_contents:
                    idcluster_list = get_idclusters_array(idcluster_upload_contents, idcluster_upload_filename)
                else:
                    idcluster_list = None


                # Load data for selected algorithm
                data = self.load_data(algorithm)

                # Extract existing CATRED traces from current figure to preserve them
                existing_catred_traces = self._extract_existing_catred_traces(current_figure)
                existing_mosaic_traces = self._extract_existing_mosaic_traces(current_figure)
                existing_mask_overlay_traces = self._extract_existing_mask_overlay_traces(current_figure)

                print(
                    f"Debug: Options update - preserving {len(existing_catred_traces)} CATRED traces"
                )
                print(
                    f"Debug: Options update - preserving {len(existing_mosaic_traces)} Mosaic traces"
                )
                print(
                    f"Debug: Options update - preserving {len(existing_mask_overlay_traces)} Mask overlay traces"
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
                    snr_threshold_lower_pzwav=snr_pzwav_lower,
                    snr_threshold_upper_pzwav=snr_pzwav_upper,
                    snr_threshold_lower_amico=snr_amico_lower,
                    snr_threshold_upper_amico=snr_amico_upper,
                    z_threshold_lower=z_lower,
                    z_threshold_upper=z_upper,
                    richness_threshold_lower=richness_lower,
                    richness_threshold_upper=richness_upper,
                    richness_mode=richness_mode,
                    flag_quality_zp=flag_quality_zp,
                    flag_quality_rs=flag_quality_rs,
                    idcluster_list=idcluster_list,
                    threshold=threshold,
                    maglim=maglim,
                    show_unmerged_clusters=show_unmerged_clusters,
                    matching_clusters=matching_clusters,
                    show_cltile_info=show_cltile_info,
                )

                # Create figure
                fig = (
                    self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio)
                    if self.figure_manager
                    else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                )

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
                    fig.update_layout(shapes=[_build_selection_shape(box_coords, relayout_data)])

                _fig_json = fig.to_json()
                print(f"Debug: Figure JSON {len(_fig_json) / 1024:.0f} KB, {len(traces)} traces, {len(data['data_detcluster_mergedcat'])} merged clusters")

                return fig, empty_phz_fig, status

            except Exception as e:
                error_status = dbc.Alert(f"Error updating: {str(e)}", color="warning")
                return dash.no_update, dash.no_update, error_status

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
                    return ['Zoom in, then click Re-render', {'color': '#6c757d'}];
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
                    return ['Zoom in, then click Re-render', {'color': '#6c757d'}];
                }

                var label = raRange.toFixed(1) + '\u00b0 \u00d7 ' + decRange.toFixed(1) + '\u00b0';
                var maxDim = Math.max(raRange, decRange);

                if (maxDim < 5.0) {
                    return ['\u2713 ' + label + ' \u2014 ready to render ovals', {'color': '#198754'}];
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
        manual_catred_data=None,
        snr_threshold_lower_pzwav=None,
        snr_threshold_upper_pzwav=None,
        snr_threshold_lower_amico=None,
        snr_threshold_upper_amico=None,
        z_threshold_lower=None,
        z_threshold_upper=None,
        richness_threshold_lower=None,
        richness_threshold_upper=None,
        richness_mode=None,
        flag_quality_zp=None,
        flag_quality_rs=None,
        idcluster_list=None,
        threshold=0.8,
        maglim=None,
        show_unmerged_clusters=False,
        matching_clusters=False,
        show_cltile_info=True,
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
                manual_catred_data=manual_catred_data,
                snr_threshold_lower_pzwav=snr_threshold_lower_pzwav,
                snr_threshold_upper_pzwav=snr_threshold_upper_pzwav,
                snr_threshold_lower_amico=snr_threshold_lower_amico,
                snr_threshold_upper_amico=snr_threshold_upper_amico,
                z_threshold_lower=z_threshold_lower,
                z_threshold_upper=z_threshold_upper,
                richness_threshold_lower=richness_threshold_lower,
                richness_threshold_upper=richness_threshold_upper,
                richness_mode=richness_mode,
                flag_quality_zp=flag_quality_zp,
                flag_quality_rs=flag_quality_rs,
                idcluster_list=idcluster_list,
                threshold=threshold,
                maglim=maglim,
                show_unmerged_clusters=show_unmerged_clusters,
                matching_clusters=matching_clusters,
                show_cltile_info=show_cltile_info,
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
                    text="Select your preferred algorithm and display options from the sidebar,<br>then click the 'Initial Render' button to generate the plot.",
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
            "Click on a MER data point above to view its PHZ_PDF"
        )

        initial_status = dbc.Alert(
            [
                html.H6("Ready to render", className="mb-1"),
                html.P(
                    "Click 'Initial Render' to begin. After that, options will update automatically while preserving your zoom level.",
                    className="mb-0",
                ),
            ],
            color="secondary",
            className="mt-2",
        )

        return initial_fig, initial_phz_fig, initial_status

    def _create_empty_phz_plot(self, message="Click on a MER data point to view its PHZ_PDF"):
        """Create empty PHZ_PDF plot with message"""
        empty_phz_fig = go.Figure()
        empty_phz_fig.update_layout(
            title="PHZ_PDF Plot",
            xaxis_title="Redshift",
            yaxis_title="Probability Density",
            margin=dict(l=40, r=20, t=40, b=40),
            showlegend=False,
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
                    font=dict(size=14, color="gray"),
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

    def _extract_existing_catred_traces(self, current_figure):
        """Extract existing CATRED traces from current figure"""
        existing_catred_traces = []
        if current_figure and "data" in current_figure:
            for trace in current_figure["data"]:
                if (
                    isinstance(trace, dict)
                    and "name" in trace
                    and trace["name"]
                    and trace["name"].startswith("CATRED")
                ):
                    # Convert dict to Scattergl object for consistency
                    existing_trace = go.Scattergl(
                        x=trace.get("x", []),
                        y=trace.get("y", []),
                        mode=trace.get("mode", "markers"),
                        marker=trace.get("marker", {}),
                        name=trace.get("name", "CATRED Data"),
                        text=trace.get("text", []),
                        customdata=trace.get("customdata", None),
                        hovertemplate=trace.get("hovertemplate", None),
                        hoverlabel=trace.get("hoverlabel", None),
                        hoverinfo=trace.get("hoverinfo", "text"),
                        legendgroup=trace.get("legendgroup", None),
                        opacity=trace.get("opacity", None),
                        showlegend=trace.get("showlegend", True),
                        visible=trace.get("visible", True),
                    )
                    existing_catred_traces.append(existing_trace)
        return existing_catred_traces

    def _extract_existing_mosaic_traces(self, current_figure):
        """Extract existing mosaic traces from current figure"""
        existing_mosaic_traces = []
        if current_figure and "data" in current_figure:
            for trace in current_figure["data"]:
                if (
                    isinstance(trace, dict)
                    and "name" in trace
                    and trace["name"]
                    and "Mosaic" in trace["name"]
                ):
                    # Preserve the original trace type (Image, Heatmap, etc.)
                    trace_type = trace.get("type", "image")

                    if trace_type == "image":
                        existing_trace = go.Image(
                            source=trace.get("source"),
                            x0=trace.get("x0"),
                            y0=trace.get("y0"),
                            dx=trace.get("dx"),
                            dy=trace.get("dy"),
                            name=trace.get("name", "Mosaic Image"),
                            opacity=trace.get("opacity", 1.0),
                            layer=trace.get("layer", "below"),
                        )
                    elif trace_type == "heatmap":
                        existing_trace = go.Heatmap(
                            z=trace.get("z"),
                            x=trace.get("x"),
                            y=trace.get("y"),
                            name=trace.get("name", "Mosaic Image"),
                            opacity=trace.get("opacity", 1.0),
                            colorscale=trace.get("colorscale", "gray"),
                            showscale=trace.get("showscale", False),
                        )
                    else:
                        # Keep original trace as-is for unknown types
                        existing_trace = trace

                    existing_mosaic_traces.append(existing_trace)
                    print(
                        f"Debug: Preserved existing mosaic trace: {trace['name']} (type: {trace_type})"
                    )
        return existing_mosaic_traces

    def _extract_existing_mask_overlay_traces(self, current_figure):
        """Extract existing mask overlay traces from current figure"""
        existing_mask_overlay_traces = []
        if current_figure and "data" in current_figure:
            for trace in current_figure["data"]:
                if (
                    isinstance(trace, dict)
                    and "name" in trace
                    and trace["name"]
                    and (
                        "Mask overlay" in trace["name"]
                        or trace["name"] == "Mask Colorbar"
                    )
                ):
                    trace_type = trace.get("type", "scatter")
                    if trace_type == "scatter":
                        if trace.get("name") == "Mask Colorbar":
                            # Colorbar-only scatter — must preserve the marker dict
                            # (contains colorscale, cmin/cmax, and colorbar spec).
                            existing_trace = go.Scatter(
                                x=trace.get("x"),
                                y=trace.get("y"),
                                mode=trace.get("mode", "markers"),
                                showlegend=trace.get("showlegend", False),
                                hoverinfo=trace.get("hoverinfo", "skip"),
                                name=trace.get("name", "Mask Colorbar"),
                                marker=trace.get("marker", {}),
                            )
                        else:
                            existing_trace = go.Scatter(
                                x=trace.get("x", []),
                                y=trace.get("y", []),
                                mode=trace.get("mode", "lines"),
                                fill=trace.get("fill"),
                                fillcolor=trace.get("fillcolor", "rgba(0,0,0,0)"),
                                line=trace.get("line", {}),
                                name=trace.get("name", "Mask overlay"),
                                opacity=trace.get("opacity", 0.6),
                                hoverinfo=trace.get("hoverinfo", "text"),
                                showlegend=trace.get("showlegend", False),
                            )
                    elif trace_type == "heatmap":
                        existing_trace = go.Heatmap(
                            z=trace.get("z"),
                            x=trace.get("x"),
                            y=trace.get("y"),
                            name=trace.get("name", "Mask overlay"),
                            opacity=trace.get("opacity", 0.6),
                            colorscale=trace.get("colorscale", "viridis"),
                            showscale=trace.get("showscale", False),
                        )
                    else:
                        existing_trace = trace
                    existing_mask_overlay_traces.append(existing_trace)
                    print(
                        f"Debug: Preserved existing mask overlay trace: {trace['name']} (type: {trace_type})"
                    )
        return existing_mask_overlay_traces

    def _calculate_filtered_count(self, cluster_data, snr_lower, snr_upper, z_lower, z_upper):
        """Calculate filtered cluster count based on SNR range"""
        if snr_lower is None and snr_upper is None:
            cluster_data_1 = cluster_data
        elif snr_lower is not None and snr_upper is not None:
            cluster_data_1 = cluster_data[
                (cluster_data["SNR_CLUSTER"] >= snr_lower)
                & (cluster_data["SNR_CLUSTER"] <= snr_upper)
            ]
        elif snr_upper is not None and snr_lower is None:
            cluster_data_1 = cluster_data[cluster_data["SNR_CLUSTER"] <= snr_upper]
        elif snr_lower is not None and snr_upper is None:
            cluster_data_1 = cluster_data[cluster_data["SNR_CLUSTER"] >= snr_lower]

        if z_lower is None and z_upper is None:
            return len(cluster_data_1)
        elif z_lower is not None and z_upper is not None:
            return len(
                cluster_data_1[
                    (cluster_data_1["Z_CLUSTER"] >= z_lower)
                    & (cluster_data_1["Z_CLUSTER"] <= z_upper)
                ]
            )
        elif z_upper is not None and z_lower is None:
            return len(cluster_data_1[cluster_data_1["Z_CLUSTER"] <= z_upper])
        elif z_lower is not None and z_upper is None:
            return len(cluster_data_1[cluster_data_1["Z_CLUSTER"] >= z_lower])

    def _calculate_filtered_count_both(
        self,
        cluster_data,
        snr_pzwav_lower,
        snr_pzwav_upper,
        snr_amico_lower,
        snr_amico_upper,
        z_lower,
        z_upper,
    ):
        """Calculate filtered cluster count for BOTH mode with separate SNR ranges"""
        # Filter PZWAV clusters (DET_CODE_NB == 2)
        if "DET_CODE_NB" in cluster_data.dtype.names:
            pzwav_data = cluster_data[cluster_data["DET_CODE_NB"] == 2]
        else:
            pzwav_data = cluster_data
        if snr_pzwav_lower is not None and snr_pzwav_upper is not None:
            pzwav_data = pzwav_data[
                (pzwav_data["SNR_CLUSTER"] >= snr_pzwav_lower)
                & (pzwav_data["SNR_CLUSTER"] <= snr_pzwav_upper)
            ]

        # Filter AMICO clusters (DET_CODE_NB == 1)
        if "DET_CODE_NB" in cluster_data.dtype.names:
            amico_data = cluster_data[cluster_data["DET_CODE_NB"] == 1]
        else:
            amico_data = cluster_data[:0]  # empty — avoid double-counting when column absent
        if snr_amico_lower is not None and snr_amico_upper is not None:
            amico_data = amico_data[
                (amico_data["SNR_CLUSTER"] >= snr_amico_lower)
                & (amico_data["SNR_CLUSTER"] <= snr_amico_upper)
            ]

        # Combine filtered data
        combined_data = np.concatenate([pzwav_data, amico_data])

        # Apply redshift filter
        if z_lower is not None and z_upper is not None:
            combined_data = combined_data[
                (combined_data["Z_CLUSTER"] >= z_lower) & (combined_data["Z_CLUSTER"] <= z_upper)
            ]
        elif z_lower is not None:
            combined_data = combined_data[combined_data["Z_CLUSTER"] >= z_lower]
        elif z_upper is not None:
            combined_data = combined_data[combined_data["Z_CLUSTER"] <= z_upper]

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
