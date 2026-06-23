"""
Cluster modal callbacks for cluster visualization.

Handles cluster selection, modal dialog interactions, and cluster-specific actions
like cutout generation, PHZ analysis, and data export.
"""

import dash  # type: ignore[import]
import dash_bootstrap_components as dbc  # type: ignore[import]
import numpy as np
import os
import pandas as pd
import plotly.graph_objs as go  # type: ignore[import]
import dash
from dash import Input, Output, State, callback_context, html
from typing import Any, Dict, List, Optional, Tuple


class ClusterModalCallbacks:
    """Handles cluster modal and action callbacks"""

    def __init__(
        self, app, data_loader, catred_handler, mosaic_handler, trace_creator, figure_manager
    ):
        """
        Initialize cluster modal callbacks.

        Args:
            app: Dash application instance
            data_loader: DataLoader instance for data operations
            trace_creator: TraceCreator instance for trace creation
            figure_manager: FigureManager instance for figure layout
        """
        self.app = app
        self.data_loader = data_loader
        self.catred_handler = catred_handler
        self.mosaic_handler = mosaic_handler
        self.trace_creator = trace_creator
        self.figure_manager = figure_manager

        # Store selected cluster data
        self.selected_cluster = None

        self.setup_callbacks()

    def setup_callbacks(self):
        """Setup all cluster modal callbacks"""
        self._setup_cluster_click_callback()
        self._setup_modal_close_callbacks()
        self._setup_cutout_toggle_callback()
        self._setup_catred_visibility_callback()
        self._setup_action_callbacks()
        self._setup_sidebar_callbacks()
        self._setup_tab_callbacks()  # 🆕 Add tab callbacks
        self._setup_cluster_tagging_callbacks()
        self._setup_parameter_sync_callbacks()
        self._setup_trace_management_callbacks()  # 🆕 Add trace management callbacks
        self._setup_selection_box_callback()
        self._setup_cluster_members_callback()

    def _setup_cluster_click_callback(self):
        """Setup callback to detect cluster clicks and show in cluster tab."""

        @self.app.callback(
            [
                Output("cluster-no-selection", "style"),
                Output("cluster-selected-content", "style"),
                Output("cluster-info-display-tab", "children"),
                Output("analysis-tabs", "active_tab"),
                Output("selected-cluster-merged-record", "data"),
                Output("selected-cluster-box-coords", "data"),
            ],
            [Input("cluster-plot", "clickData"),
             Input("aladin-click-store", "data")],
            [State("algorithm-dropdown", "value")],
            prevent_initial_call=True,
        )
        def handle_cluster_click(clickData, aladin_click, algorithm):
            """Handle cluster point clicks from Plotly figure or Aladin Lite."""
            ctx = callback_context
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

            no_change = (dash.no_update,) * 6

            # --- Aladin Lite click ---
            if triggered_id == "aladin-click-store" and aladin_click:
                ra = aladin_click.get("ra")
                dec = aladin_click.get("dec")
                name = aladin_click.get("name", "")
                if ra is None or dec is None:
                    return no_change

                synthetic_point = {"x": ra, "y": dec, "customdata": [None, None, None, name]}
                merged_record, resolution_note = self._resolve_merged_record_for_click(
                    synthetic_point, algorithm
                )
                merged_cluster_id = (
                    merged_record.get("ID_UNIQUE_CLUSTER") if merged_record is not None else None
                )
                snr = merged_record.get("SNR_CLUSTER", "N/A") if merged_record else "N/A"
                redshift = merged_record.get("Z_CLUSTER", "N/A") if merged_record else "N/A"

                self.selected_cluster = {
                    "ra": ra, "dec": dec, "snr": snr, "redshift": redshift,
                    "algorithm": algorithm, "trace_name": "Aladin",
                    "merged_record": merged_record, "merged_cluster_id": merged_cluster_id,
                    "resolution_note": resolution_note,
                }
                print(f"🔭 Aladin cluster clicked: RA={ra:.3f}, Dec={dec:.3f}")

                snr_str = f"{snr:.2f}" if isinstance(snr, float) else str(snr)
                z_str = f"{redshift:.2f}" if isinstance(redshift, float) else str(redshift)
                tab_content = self._build_cluster_tab_content(
                    ra, dec, snr_str, z_str, algorithm, merged_cluster_id, resolution_note
                )
                return (
                    {"display": "none"}, {"display": "block"},
                    tab_content, "cluster-tab", merged_record,
                    {"ra": ra, "dec": dec},
                )

            # --- Plotly figure click ---
            if not clickData or not clickData.get("points"):
                return no_change
            point = clickData["points"][0]
            curve_number = point.get("curveNumber", 0)

            if "customdata" in point and point["customdata"]:
                customdata = point.get("customdata", [])
                customdata = [customdata] if not isinstance(customdata, list) else customdata

                if len(customdata) >= 2:
                    ra = point.get("x", "N/A")
                    dec = point.get("y", "N/A")
                    snr = customdata[0] if len(customdata) > 0 else "N/A"
                    redshift = customdata[1] if len(customdata) > 1 else "N/A"
                    merged_record, resolution_note = self._resolve_merged_record_for_click(
                        point, algorithm
                    )
                    merged_cluster_id = (
                        merged_record.get("ID_UNIQUE_CLUSTER") if merged_record is not None else None
                    )

                    trace_name = f"Curve {curve_number}"
                    if "text" in point and point["text"] and "Tile" in str(point["text"]):
                        trace_name = "Individual Tile Cluster"

                    self.selected_cluster = {
                        "ra": ra, "dec": dec, "snr": snr, "redshift": redshift,
                        "algorithm": algorithm, "trace_name": trace_name,
                        "curve_number": curve_number, "point_data": point,
                        "merged_record": merged_record, "merged_cluster_id": merged_cluster_id,
                        "resolution_note": resolution_note,
                    }

                    print(
                        f"🎯 Cluster clicked: RA={ra:.3f}, Dec={dec:.3f}, SNR={snr:.2f}, z={redshift:.2f}"
                    )

                    snr_str = f"{snr:.2f}" if isinstance(snr, float) else str(snr)
                    z_str = f"{redshift:.2f}" if isinstance(redshift, float) else str(redshift)
                    tab_content = self._build_cluster_tab_content(
                        ra, dec, snr_str, z_str, algorithm, merged_cluster_id, resolution_note
                    )
                    return (
                        {"display": "none"}, {"display": "block"},
                        tab_content, "cluster-tab", merged_record,
                        {"ra": ra, "dec": dec},
                    )

            return no_change

    def _build_cluster_tab_content(
        self, ra, dec, snr_str, z_str, algorithm, merged_cluster_id, resolution_note
    ):
        """Build the cluster info tab content layout (shared by Plotly and ESA Sky clicks)."""
        return [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Strong("Coordinates", className="text-primary"),
                            html.Div(
                                [f"RA: {ra:.3f}°", html.Br(), f"Dec: {dec:.3f}°"]
                                if isinstance(ra, float) else [f"RA: {ra}", html.Br(), f"Dec: {dec}"],
                                className="mt-1",
                            ),
                        ],
                        width=6,
                    ),
                    dbc.Col(
                        [
                            html.Strong("Properties", className="text-primary"),
                            html.Div(
                                [f"z: {z_str}", html.Br(), f"SNR: {snr_str}", html.Br()],
                                className="mt-1",
                            ),
                        ],
                        width=6,
                    ),
                ]
            ),
            html.Hr(className="my-2"),
            html.Div([html.Strong("Source: ", className="text-primary"), f"{algorithm}"]),
            html.Div(
                [
                    html.Strong("Merged Candidate ID: ", className="text-primary"),
                    str(merged_cluster_id) if merged_cluster_id is not None else "Not resolved",
                ]
            ),
            html.Small(resolution_note, className="text-muted"),
        ]

    def _setup_modal_close_callbacks(self):
        """Setup callbacks to close the modal"""

        @self.app.callback(
            [
                Output("cluster-action-modal", "is_open", allow_duplicate=True),
                Output("selected-cluster-box-coords", "data", allow_duplicate=True),
            ],
            [
                Input("cluster-modal-close", "n_clicks"),
                Input("cluster-modal-close-footer", "n_clicks"),
            ],
            [State("cluster-action-modal", "is_open")],
            prevent_initial_call=True,
        )
        def close_modal(close_clicks, footer_clicks, is_open):
            """Close the modal when close buttons are clicked"""
            if close_clicks or footer_clicks:
                return False, None
            return dash.no_update, dash.no_update

    def _setup_selection_box_callback(self):
        """Setup clientside callback to overplot selected cluster as a square-open marker."""
        self.app.clientside_callback(
            """
            function(box_coords, figure) {
                if (!figure || !figure.data) return window.dash_clientside.no_update;

                var TRACE_NAME = "__selected_cluster__";
                var traces = figure.data.filter(function(t) { return t.name !== TRACE_NAME; });

                if (box_coords && box_coords.ra !== undefined) {
                    traces = traces.concat([{
                        type: "scatter",
                        x: [box_coords.ra],
                        y: [box_coords.dec],
                        mode: "markers",
                        marker: {
                            symbol: "square-open",
                            size: 18,
                            color: "yellow",
                            line: { color: "yellow", width: 2 }
                        },
                        name: TRACE_NAME,
                        showlegend: false,
                        hoverinfo: "skip"
                    }]);
                }

                return Object.assign({}, figure, { data: traces });
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input("selected-cluster-box-coords", "data"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

    def _setup_cutout_toggle_callback(self):
        """Setup callback to toggle cutout options"""

        @self.app.callback(
            Output("cutout-options-collapse", "is_open"),
            [Input("cluster-cutout-button", "n_clicks")],
            [State("cutout-options-collapse", "is_open")],
            prevent_initial_call=True,
        )
        def toggle_cutout_options(n_clicks, is_open):
            """Toggle cutout options when cutout button is clicked"""
            if n_clicks:
                return not is_open
            return is_open

    def _setup_catred_visibility_callback(self):
        @self.app.callback(
            Output("catred-box-options-collapse", "is_open"),
            [Input("cluster-catred-box-button", "n_clicks")],
            [State("catred-box-options-collapse", "is_open")],
            prevent_initial_call=True,
        )
        def toggle_catred_box_options(n_clicks, is_open):
            """Toggle catred box options when catred box button is clicked"""
            if n_clicks:
                return not is_open
            return is_open

    def _setup_action_callbacks(self):
        """Setup callbacks for cluster action buttons"""

        @self.app.callback(
            Output("status-info", "children", allow_duplicate=True),
            [
                Input("cluster-cutout-button", "n_clicks"),
                Input("cluster-phz-button", "n_clicks"),
                Input("cluster-catred-box-button", "n_clicks"),
                Input("cluster-export-button", "n_clicks"),
            ],
            [State("cutout-size-input", "value"), State("cutout-data-type", "value")],
            prevent_initial_call=True,
        )
        def handle_cluster_actions(
            cutout_clicks, phz_clicks, catred_box_clicks, export_clicks, cutout_size, cutout_type
        ):
            """Handle various cluster action button clicks"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update

            button_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if not self.selected_cluster:
                return dbc.Alert("⚠️ No cluster selected", color="warning")

            cluster = self.selected_cluster

            if button_id == "cluster-cutout-button":
                # Placeholder for cutout generation
                status_msg = dbc.Alert(
                    [
                        html.H6("🔬 Cutout Generation Requested", className="mb-2"),
                        html.P(
                            [
                                f"📍 Target: RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}°",
                                html.Br(),
                                f"📏 Size: {cutout_size} arcmin",
                                html.Br(),
                                f"📊 Type: {cutout_type.title()} data",
                                html.Br(),
                                f"🎯 Algorithm: {cluster['algorithm']}",
                            ]
                        ),
                        html.Small(
                            "Cutout generation functionality will be implemented here",
                            className="text-muted",
                        ),
                    ],
                    color="info",
                )

                print(
                    f"🔬 Cutout requested: RA={cluster['ra']}, Dec={cluster['dec']}, Size={cutout_size}arcmin, Type={cutout_type}"
                )
                return status_msg

            elif button_id == "cluster-phz-button":
                # Placeholder for PHZ analysis
                status_msg = dbc.Alert(
                    [
                        html.H6("📈 PHZ Analysis Requested", className="mb-2"),
                        html.P(
                            [
                                f"🎯 Target: RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}°",
                                html.Br(),
                                f"🔢 Current z: {cluster['redshift']:.2f}",
                                html.Br(),
                                f"📊 SNR: {cluster['snr']:.2f}",
                            ]
                        ),
                        html.Small(
                            "Photometric redshift analysis will be implemented here",
                            className="text-muted",
                        ),
                    ],
                    color="success",
                )

                print(
                    f"📈 PHZ analysis requested for cluster at RA={cluster['ra']}, Dec={cluster['dec']}"
                )
                return status_msg

            elif button_id == "cluster-catred-box-button":
                # Placeholder for CATRED box viewing
                status_msg = dbc.Alert(
                    [
                        html.H6("🖼️ CATRED Box Requested", className="mb-2"),
                        html.P(
                            [
                                f"📍 Target: RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}°, z {cluster['redshift']:.3f}",
                                html.Br(),
                                f"🔍 Algorithm: {cluster['algorithm']}",
                            ]
                        ),
                        html.Small(
                            "CATRED box functionality will be implemented here",
                            className="text-muted",
                        ),
                    ],
                    color="primary",
                )

                print(
                    f"🖼️ CATRED box requested for cluster at RA={cluster['ra']:.3f}°, Dec={cluster['dec']:.3f}°"
                )
                return status_msg

            elif button_id == "cluster-export-button":
                # Placeholder for data export
                status_msg = dbc.Alert(
                    [
                        html.H6("💾 Data Export Requested", className="mb-2"),
                        html.P(
                            [
                                f"📍 Target: RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}°",
                                html.Br(),
                                f"📊 Data: SNR={cluster['snr']:.2f}, z={cluster['redshift']:.2f}",
                            ]
                        ),
                        html.Small(
                            "Data export functionality will be implemented here",
                            className="text-muted",
                        ),
                    ],
                    color="warning",
                )

                print(
                    f"💾 Data export requested for cluster at RA={cluster['ra']:.3f}°, Dec={cluster['dec']:.3f}°"
                )
                return status_msg

            return dash.no_update

    def _setup_sidebar_callbacks(self):
        """Setup sidebar-specific callbacks"""

        # Toggle cutout options in sidebar
        @self.app.callback(
            Output("sidebar-cutout-options", "is_open"),
            [Input("quick-cutout-button", "n_clicks")],
            [State("sidebar-cutout-options", "is_open")],
            prevent_initial_call=True,
        )
        def toggle_sidebar_cutout_options(n_clicks, is_open):
            """Toggle sidebar cutout options"""
            if n_clicks:
                return not is_open
            return is_open

        # Toggle CATRED box options in sidebar
        @self.app.callback(
            Output("sidebar-catred-box-options", "is_open"),
            [Input("quick-catred-box-button", "n_clicks")],
            [State("sidebar-catred-box-options", "is_open")],
            prevent_initial_call=True,
        )
        def toggle_sidebar_catred_box_options(n_clicks, is_open):
            """Toggle sidebar CATRED box options"""
            if n_clicks:
                return not is_open
            return is_open

        # Handle sidebar action buttons
        @self.app.callback(
            Output("status-info", "children", allow_duplicate=True),
            [
                Input("sidebar-generate-cutout", "n_clicks"),
                Input("quick-phz-button", "n_clicks"),
                Input("quick-catred-box-button", "n_clicks"),
                Input("cluster-more-options-button", "n_clicks"),
            ],
            [State("sidebar-cutout-size", "value"), State("sidebar-cutout-type", "value")],
            prevent_initial_call=True,
        )
        def handle_sidebar_actions(
            cutout_clicks, phz_clicks, catred_box_clicks, more_clicks, cutout_size, cutout_type
        ):
            """Handle sidebar action button clicks"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update

            button_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if not self.selected_cluster:
                return dbc.Alert("⚠️ No cluster selected", color="warning")

            cluster = self.selected_cluster

            if button_id == "sidebar-generate-cutout":
                status_msg = dbc.Alert(
                    [
                        html.H6("🔬 Generating Cutout...", className="mb-2"),
                        html.P(
                            [
                                f"📍 RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}°",
                                html.Br(),
                                f"📏 {cutout_size} arcmin | 📊 {cutout_type.title()}",
                            ]
                        ),
                        html.Small("Cutout generation in progress...", className="text-muted"),
                    ],
                    color="info",
                )

                print(
                    f"🔬 Sidebar cutout: RA={cluster['ra']:.3f}°, Dec={cluster['dec']:.3f}°, Size={cutout_size}, Type={cutout_type}"
                )
                return status_msg

            elif button_id == "quick-phz-button":
                status_msg = dbc.Alert(
                    [
                        html.H6("📈 PHZ Analysis", className="mb-2"),
                        html.P(f"🎯 z={cluster['redshift']:.3f} | SNR={cluster['snr']:.3f}"),
                    ],
                    color="success",
                )
                return status_msg

            elif button_id == "quick-catred-box-button":
                status_msg = dbc.Alert(
                    [
                        html.H6("🖼️ Loading CATRED Box...", className="mb-2"),
                        html.P(f"📍 RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}°"),
                    ],
                    color="primary",
                )
                return status_msg

            elif button_id == "cluster-more-options-button":
                # This could open the full modal for advanced options
                status_msg = dbc.Alert(
                    [
                        html.H6("⚙️ More Options", className="mb-2"),
                        html.P("Advanced analysis options available"),
                    ],
                    color="secondary",
                )
                return status_msg

            return dash.no_update

    def _setup_tab_callbacks(self):
        """Setup tab switching and tab-specific callbacks"""

        # Tab content switching
        @self.app.callback(
            [
                Output("phz-tab-content", "style"),
                Output("cluster-tab-content", "style"),
                Output("file-config-tab-content", "style"),
            ],
            [Input("analysis-tabs", "active_tab")],
            prevent_initial_call=True,
        )
        def switch_tab_content(active_tab):
            """Switch between PHZ, cluster analysis, and file config tab content"""
            if active_tab == "phz-tab":
                return {"display": "block"}, {"display": "none"}, {"display": "none"}
            elif active_tab == "cluster-tab":
                return {"display": "none"}, {"display": "block"}, {"display": "none"}
            elif active_tab == "file-config-tab":
                return {"display": "none"}, {"display": "none"}, {"display": "block"}
            return dash.no_update, dash.no_update, dash.no_update

        # Toggle tab options - only one collapse open at a time
        @self.app.callback(
            [
                Output("tab-cutout-options", "is_open"),
                Output("tab-catred-box-options", "is_open"),
                Output("tab-mask-cutout-options", "is_open"),
                Output("tab-tagging-options", "is_open"),
                Output("tab-cluster-members-options", "is_open"),
            ],
            [
                Input("tab-cutout-button", "n_clicks"),
                Input("tab-catred-box-button", "n_clicks"),
                Input("tab-mask-cutout-button", "n_clicks"),
                Input("tab-tag-panel-button", "n_clicks"),
                Input("tab-cluster-members-button", "n_clicks"),
            ],
            [
                State("tab-cutout-options", "is_open"),
                State("tab-catred-box-options", "is_open"),
                State("tab-mask-cutout-options", "is_open"),
                State("tab-tagging-options", "is_open"),
                State("tab-cluster-members-options", "is_open"),
            ],
            prevent_initial_call=True,
        )
        def toggle_tab_options(
            cutout_clicks, catred_clicks, mask_clicks, tagging_clicks, members_clicks,
            cutout_open, catred_open, mask_open, tagging_open, members_open,
        ):
            """Toggle tab options - only one collapse open at a time"""
            ctx = dash.callback_context
            if not ctx.triggered:
                return cutout_open, catred_open, mask_open, tagging_open, members_open

            button_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if button_id == "tab-cutout-button":
                return not cutout_open, False, False, False, False
            elif button_id == "tab-catred-box-button":
                return False, not catred_open, False, False, False
            elif button_id == "tab-mask-cutout-button":
                return False, False, not mask_open, False, False
            elif button_id == "tab-tag-panel-button":
                return False, False, False, not tagging_open, False
            elif button_id == "tab-cluster-members-button":
                return False, False, False, False, not members_open

            return cutout_open, catred_open, mask_open, tagging_open, members_open

        # Handle tab action buttons
        @self.app.callback(
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("phz-pdf-plot", "figure", allow_duplicate=True),
                Output("cluster-analysis-results", "children"),
                Output("status-info", "children", allow_duplicate=True),
            ],
            [
                Input("tab-generate-cutout", "n_clicks"),
                Input("tab-view-catred-box", "n_clicks"),
                Input("tab-generate-mask-cutout", "n_clicks"),
            ],
            #
            [
                State("algorithm-dropdown", "value"),
                State("snr-range-slider-pzwav", "value"),
                State("snr-range-slider-amico", "value"),
                State("redshift-range-slider", "value"),
                State("polygon-switch", "value"),
                State("mer-switch", "value"),
                State("aspect-ratio-switch", "value"),
                State("unmerged-clusters-switch", "value"),
                State("cltile-info-switch", "value"),
                #
                State("tab-cutout-size", "value"),
                State("tab-cutout-type", "value"),
                State("tab-cutout-opacity", "value"),
                State("tab-cutout-colorscale", "value"),
                #
                State("tab-catred-box-size", "value"),
                State("tab-catred-redshift-bin-width", "value"),
                State("tab-catred-mask-threshold", "value"),
                State("tab-catred-maglim", "value"),
                State("tab-catred-marker-size", "value"),
                State("tab-catred-marker-size-custom", "value"),
                State("tab-catred-marker-color-picker", "value"),
                #
                State("tab-mask-cutout-size", "value"),
                State("tab-mask-cutout-opacity", "value"),
                #
                State("catred-mode-switch", "value"),
                State("catred-threshold-slider", "value"),
                State("magnitude-limit-slider", "value"),
                State("cluster-plot", "relayoutData"),
                State("cluster-plot", "figure"),
            ],
            prevent_initial_call=True,
            background=True,
            running=[
                (
                    Output("tab-action-progress-container", "style"),
                    {"display": "block"},
                    {"display": "none"},
                ),
                (Output("tab-generate-cutout", "disabled"), True, False),
                (Output("tab-view-catred-box", "disabled"), True, False),
                (Output("tab-generate-mask-cutout", "disabled"), True, False),
            ],
            progress=[
                Output("tab-action-progress", "value"),
                Output("tab-action-label", "children"),
            ],
        )
        def handle_tab_actions(
            set_progress,
            cutout_clicks,
            catred_box_clicks,
            mask_cutout_clicks,
            algorithm,
            snr_range_pzwav,
            snr_range_amico,
            redshift_range,
            show_polygons,
            show_mer_tiles,
            free_aspect_ratio,
            show_unmerged_clusters,
            show_cltile_info,
            cutout_size,
            cutout_type,
            cutout_opacity,
            cutout_colorscale,
            catred_box_size,
            catred_redshift_bin_width,
            catred_mask_threshold,
            catred_maglim,
            catred_marker_size_option,
            catred_marker_size_custom,
            catred_marker_color,
            mask_cutout_size,
            mask_cutout_opacity,
            catred_masked,
            threshold,
            maglim,
            relayout_data,
            current_figure,
        ):
            """Handle tab action button clicks"""
            set_progress((5, "Initializing..."))
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update

            button_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if not self.selected_cluster:
                return (
                    dash.no_update,
                    dash.no_update,
                    html.P("⚠️ No cluster selected", className="text-warning"),
                    dbc.Alert("⚠️ No cluster selected", color="warning"),
                )

            cluster = self.selected_cluster

            set_progress((20, f"Loading {algorithm} data..."))
            print(f"Loading data for algorithm: {algorithm}")
            data = self.data_loader.load_data(select_algorithm=algorithm)
            print("Data loaded successfully.")
            set_progress((50, "Processing..."))

            if button_id == "tab-generate-cutout":
                # Analysis results for the tab
                results_content = dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.H6(
                                    [html.I(className="fas fa-crop me-2"), "Cutout Generation"],
                                    className="mb-0 text-primary",
                                )
                            ]
                        ),
                        dbc.CardBody(
                            [
                                html.P(
                                    [
                                        html.Strong("Target: "),
                                        f"RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}°",
                                        html.Br(),
                                        html.Strong("Size: "),
                                        f"{cutout_size} arcmin",
                                        html.Br(),
                                        html.Strong("Type: "),
                                        cutout_type.title(),
                                        html.Br(),
                                        html.Strong("Status: "),
                                        html.Span("In Progress...", className="text-info"),
                                    ]
                                )
                            ]
                        ),
                    ]
                )

                clickdata = {
                    "cluster_ra": cluster["ra"],
                    "cluster_dec": cluster["dec"],
                    "cutout_size": cutout_size,  # cutout size in arcmin
                    "cutout_type": cutout_type,
                    #  'cutout_opacity': cutout_opacity,
                    #  'cutout_colorscale': cutout_colorscale,
                    "nclicks": cutout_clicks,
                }

                if cutout_type == "mermosaic":
                    if self.mosaic_handler:
                        set_progress((65, "Fetching mosaic cutout tiles..."))
                        mosaic_cutout_trace = self.mosaic_handler.create_mosaic_cutout_trace(
                            data=data,
                            clickdata=clickdata,
                            opacity=cutout_opacity,
                            colorscale=cutout_colorscale,
                        )

                        if mosaic_cutout_trace:
                            # Add mosaic traces to current figure with proper layering
                            if current_figure and "data" in current_figure:
                                # Remove existing mosaic traces first
                                existing_traces = [
                                    trace
                                    for trace in current_figure["data"]
                                    if not (trace.get("name", "").startswith("MER-Mosaic cutout"))
                                ]

                                # Separate traces by type to maintain proper layering order
                                polygon_traces = []
                                mosaic_traces = []
                                mask_overlay_traces = []
                                catred_traces = []
                                cluster_traces = []
                                other_traces = []

                                for trace in existing_traces:
                                    trace_name = trace.get("name", "")
                                    if "MER-Tile" in trace_name or (
                                        "Tile" in trace_name
                                        and (
                                            "CORE" in trace_name
                                            or "LEV1" in trace_name
                                            or "MerTile" in trace_name
                                        )
                                    ):
                                        polygon_traces.append(trace)
                                    elif "Mosaic" in trace_name:
                                        mosaic_traces.append(trace)
                                    elif "Mask overlay" in trace_name:
                                        mask_overlay_traces.append(trace)
                                    elif "CATRED" in trace_name:
                                        catred_traces.append(trace)
                                    elif any(
                                        keyword in trace_name
                                        for keyword in ["Merged", "Tile", "clusters"]
                                    ):
                                        cluster_traces.append(trace)
                                    else:
                                        other_traces.append(trace)

                                # Layer order: polygons (bottom) → mosaic → mosaic cutout → mask overlays → CATRED → other → cluster traces (top)
                                new_data = (
                                    polygon_traces
                                    + mosaic_traces
                                    + [mosaic_cutout_trace]
                                    + mask_overlay_traces
                                    + catred_traces
                                    + other_traces
                                    + cluster_traces
                                )
                                current_figure["data"] = new_data

                                print(f"✓ Added mosaic cutout trace as 2nd layer from bottom")
                                print(
                                    f"   -> Layer order: {len(polygon_traces)} polygons, "
                                    f"{len(mosaic_traces)} mosaics, 1 mosaic cutout, "
                                    f"{len(mask_overlay_traces)} Mask overlay, {len(catred_traces)} CATRED, "
                                    f"{len(other_traces)} other, {len(cluster_traces)} clusters (top)"
                                )
                            else:
                                print("⚠️  No current figure data to update")
                        else:
                            print("ℹ️  No mosaic images found for current zoom window")
                    else:
                        print("❌ No mosaic handler available")

                # if self.figure_manager:
                #     fig = self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio)
                # else:
                #     fig = self._create_fallback_figure(traces, algorithm, free_aspect_ratio)

                # # Preserve zoom state
                # if self.figure_manager:
                #     self.figure_manager.preserve_zoom_state(fig, relayout_data)
                # else:
                #     self._preserve_zoom_state_fallback(fig, relayout_data)

                empty_phz_fig = self._create_empty_phz_plot()

                # Status message
                status_msg = dbc.Alert(
                    [
                        html.H6("🔬 Cutout generated", className="mb-2"),
                        html.P(
                            f"📍 RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}° | 📏 {cutout_size} arcmin"
                        ),
                    ],
                    color="info",
                )

                print(
                    f"🔬 Tab cutout: RA={cluster['ra']:.3f}°, Dec={cluster['dec']:.3f}°, Size={cutout_size}, Type={cutout_type}"
                )
                return current_figure, empty_phz_fig, results_content, status_msg

            elif button_id == "tab-view-catred-box":
                results_content = dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.H6(
                                    [
                                        html.I(className="fas fa-magnifying-glass me-2"),
                                        "CATRED Box View",
                                    ],
                                    className="mb-0 text-primary",
                                )
                            ]
                        ),
                        dbc.CardBody(
                            [
                                html.P(
                                    [
                                        html.Strong("Target: "),
                                        f"RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}°",
                                        html.Br(),
                                        html.Strong("Box Size: "),
                                        f"{catred_box_size} arcmin",
                                        html.Br(),
                                        html.Strong("Redshift Bin Width: "),
                                        f"{catred_redshift_bin_width}",
                                        html.Br(),
                                        html.Strong("Status: "),
                                        html.Span("Loading CATRED Box...", className="text-info"),
                                    ]
                                )
                            ]
                        ),
                    ]
                )

                # Extract separate SNR values from range sliders
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

                # Determine which SNR to use based on algorithm
                if algorithm == "PZWAV":
                    snr_lower, snr_upper = snr_pzwav_lower, snr_pzwav_upper
                elif algorithm == "AMICO":
                    snr_lower, snr_upper = snr_amico_lower, snr_amico_upper
                else:  # BOTH - use PZWAV SNR (could also use both, but for simplicity)
                    snr_lower, snr_upper = snr_pzwav_lower, snr_pzwav_upper

                # Extract redshift values from redshift range slider
                redshift_lower = (
                    redshift_range[0] if redshift_range and len(redshift_range) == 2 else None
                )
                redshift_upper = (
                    redshift_range[1] if redshift_range and len(redshift_range) == 2 else None
                )

                print(f"Debug catred_redshift_bin_width received: {catred_redshift_bin_width!r}")
                
                # Extract existing CATRED traces from current figure to preserve them
                existing_catred_traces = self._extract_existing_catred_traces(current_figure)
                existing_mosaic_traces = self._extract_existing_mosaic_traces(current_figure)
                existing_mask_overlay_traces = self._extract_existing_mask_overlay_traces(
                    current_figure
                )

                # Load CATRED Box data
                box_params = self.catred_handler._extract_box_data_from_cluster_click(
                    click_data={
                        "ra": cluster["ra"],
                        "dec": cluster["dec"],
                        "redshift": cluster["redshift"],
                        "redshift_lim_lower": redshift_lower,
                        "redshift_lim_upper": redshift_upper,
                        "catred_box_size": (catred_box_size or 2.0) / 60,  # Convert arcmin to degrees; default 2 arcmin
                        "catred_redshift_bin_width": catred_redshift_bin_width,
                        "trace_marker": {
                            "size_option": catred_marker_size_option,  # 'set_size_custom' or 'set_size_kron'
                            "size_custom_value": catred_marker_size_custom,
                            "color": catred_marker_color,
                        },
                    }
                )

                # data = self.data_loader.load_data(select_algorithm=algorithm)
                set_progress((65, "Loading CATRED box data..."))
                catred_box_data = self.catred_handler.load_catred_data_clusterbox(
                    box=box_params, data=data, threshold=catred_mask_threshold, maglim=catred_maglim
                )

                set_progress((80, "Building figure..."))
                if self.trace_creator:
                    traces = self.trace_creator.create_traces(
                        data,
                        show_polygons,
                        show_mer_tiles,
                        relayout_data,
                        catred_masked,
                        catred_box_data=catred_box_data,
                        existing_catred_traces=[],
                        existing_mosaic_traces=existing_mosaic_traces,
                        existing_mask_overlay_traces=existing_mask_overlay_traces,
                        snr_threshold_lower_pzwav=snr_pzwav_lower,
                        snr_threshold_upper_pzwav=snr_pzwav_upper,
                        snr_threshold_lower_amico=snr_amico_lower,
                        snr_threshold_upper_amico=snr_amico_upper,
                        threshold=catred_mask_threshold,
                        show_unmerged_clusters=show_unmerged_clusters,
                        show_cltile_info=show_cltile_info,
                    )

                if self.figure_manager:
                    fig = self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio)
                else:
                    fig = self._create_fallback_figure(traces, algorithm, free_aspect_ratio)

                # Preserve zoom state
                if self.figure_manager:
                    self.figure_manager.preserve_zoom_state(fig, relayout_data)
                else:
                    self._preserve_zoom_state_fallback(fig, relayout_data)

                # Re-inject mosaic layout.images from the previous figure.
                # Mosaics are stored in fig.layout.images (not fig.data), so
                # _extract_existing_mosaic_traces cannot see them.  Copy them
                # directly from the current figure's layout before returning.
                if current_figure and isinstance(current_figure, dict):
                    prev_images = (
                        current_figure.get("layout", {}).get("images") or []
                    )
                    mosaic_images = [
                        img for img in prev_images
                        if isinstance(img, dict) and img.get("name", "").startswith("Mosaic")
                    ]
                    if mosaic_images:
                        existing_layout_images = list(fig.layout.images or [])
                        fig.update_layout(images=existing_layout_images + mosaic_images)
                        print(
                            f"Debug: Re-injected {len(mosaic_images)} mosaic layout images after CATRED box rebuild"
                        )

                # Re-inject Members traces dropped by the full figure rebuild
                members_traces = self._extract_existing_members_traces(current_figure)
                for t in members_traces:
                    if isinstance(t, dict):
                        fig.add_trace(go.Scattergl(
                            x=t.get("x", []), y=t.get("y", []),
                            mode=t.get("mode", "markers"),
                            marker=t.get("marker", {}),
                            name=t.get("name", ""),
                            customdata=t.get("customdata", None),
                            hovertemplate=t.get("hovertemplate", None),
                        ))
                    else:
                        fig.add_trace(t)
                if members_traces:
                    print(f"Debug: Re-injected {len(members_traces)} Members trace(s) after CATRED box rebuild")

                empty_phz_fig = self._create_empty_phz_plot()

                status_msg = dbc.Alert(
                    [
                        html.H6("🖼️ CATRED Box loaded", className="mb-2"),
                        html.P(f"📍 RA {cluster['ra']:.3f}°, Dec {cluster['dec']:.3f}°"),
                    ],
                    color="primary",
                )

                return fig, empty_phz_fig, results_content, status_msg

            elif button_id == "tab-generate-mask-cutout":
                results_content = dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.H6(
                                    [
                                        html.I(className="fas fa-layer-group me-2"),
                                        "Healpix Mask Cutout",
                                    ],
                                    className="mb-0 text-success",
                                )
                            ]
                        ),
                        dbc.CardBody(
                            [
                                html.P(
                                    [
                                        html.Strong("Current z: "),
                                        f"{cluster['redshift']:.3f}",
                                        html.Br(),
                                        html.Strong("SNR: "),
                                        f"{cluster['snr']:.3f}",
                                        html.Br(),
                                        html.Strong("Status: "),
                                        html.Span("Analysis Complete", className="text-success"),
                                    ]
                                )
                            ]
                        ),
                    ]
                )

                clickdata = {
                    "cluster_ra": cluster["ra"],
                    "cluster_dec": cluster["dec"],
                    "mask_cutout_size": mask_cutout_size,  # cutout size in arcmin
                    #  'mask_cutout_opacity': cutout_opacity,
                    "nclicks": cutout_clicks,
                }

                set_progress((65, "Creating mask overlay..."))
                if self.mosaic_handler:
                    mask_cutout_traces = []
                    if current_figure and "data" in current_figure:
                        mask_overlay_traces = [
                            trace
                            for trace in current_figure["data"]
                            if trace.get("name", "").startswith("Mask overlay")
                            and not "(cutout)" in trace.get("name", "")
                        ]

                        if len(mask_overlay_traces) > 0:
                            print(
                                f"✓ Preserving {len(mask_overlay_traces)} existing Mask overlay traces"
                            )
                        else:
                            print("✓ No existing Mask overlay traces to preserve")
                            mask_cutout_traces = (
                                self.mosaic_handler.create_mask_overlay_cutout_trace(
                                    data, clickdata, opacity=mask_cutout_opacity
                                )
                            )

                        # Add mask overlay traces to current figure with proper layering
                        if mask_cutout_traces:
                            # Remove existing mask overlay traces first
                            existing_traces = [
                                trace
                                for trace in current_figure["data"]
                                if not (trace.get("name", "").startswith("Mask overlay (cutout)"))
                            ]

                            # Separate traces by type to maintain proper layering order
                            polygon_traces = []
                            mosaic_traces = []
                            mosaic_cutout_traces = []
                            mask_overlay_traces = []
                            catred_traces = []
                            cluster_traces = []
                            other_traces = []

                            for trace in existing_traces:
                                trace_name = trace.get("name", "")
                                if "MER-Tile" in trace_name or (
                                    "Tile" in trace_name
                                    and (
                                        "CORE" in trace_name
                                        or "LEV1" in trace_name
                                        or "MerTile" in trace_name
                                    )
                                ):
                                    polygon_traces.append(trace)
                                elif "Mosaic" in trace_name and not trace_name.startswith(
                                    "MER-Mosaic cutout"
                                ):
                                    mosaic_traces.append(trace)
                                elif "Mosaic" in trace_name and trace_name.startswith(
                                    "MER-Mosaic cutout"
                                ):
                                    mosaic_cutout_traces.append(trace)
                                elif "Mask overlay" in trace_name:
                                    mask_overlay_traces.append(trace)
                                elif "CATRED" in trace_name:
                                    catred_traces.append(trace)
                                elif any(
                                    keyword in trace_name
                                    for keyword in ["Merged", "Tile", "clusters"]
                                ):
                                    cluster_traces.append(trace)
                                else:
                                    other_traces.append(trace)

                            if len(mask_overlay_traces) > 0:
                                print(
                                    f"✓ Kept {len(mask_overlay_traces)} existing Mask overlay traces"
                                )
                            else:
                                print("✓ No existing Mask overlay traces to preserve")
                                mask_overlay_traces.extend(mask_cutout_traces)

                            # Layer order: polygons (bottom) → mosaic → CATRED → other → cluster traces (top)
                            new_data = (
                                polygon_traces
                                + mosaic_traces
                                + mosaic_cutout_traces
                                + mask_overlay_traces
                                + catred_traces
                                + other_traces
                                + cluster_traces
                            )
                            current_figure["data"] = new_data

                            print(f"✓ Added mask overlay cutout trace as 4th layer from bottom")
                            print(
                                f"   -> Layer order: {len(polygon_traces)} polygons, "
                                f"{len(mosaic_traces)} mosaics, {len(mosaic_cutout_traces)} mosaic cutouts, "
                                f"{len(mask_overlay_traces)} Mask overlay, {len(catred_traces)} CATRED, "
                                f"{len(other_traces)} other, {len(cluster_traces)} clusters (top)"
                            )

                        else:
                            print("ℹ️  No mask overlay found for current selected cluster")

                    else:
                        print("⚠️  No current figure data to update")

                else:
                    print("❌ No mosaic handler available")

                empty_phz_fig = self._create_empty_phz_plot()

                status_msg = dbc.Alert(
                    [
                        html.H6("🗺️ Healpix Mask Cutout Complete", className="mb-2"),
                        html.P(f"🎯 z={cluster['redshift']:.2f} | SNR={cluster['snr']:.2f}"),
                    ],
                    color="success",
                )

                return current_figure, empty_phz_fig, results_content, status_msg

            return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    def _setup_cluster_tagging_callbacks(self):
        """Setup callbacks for cluster candidate tagging and CSV save workflow."""

        @self.app.callback(
            Output("tag-panel-cluster-preview", "children"),
            [Input("selected-cluster-merged-record", "data")],
            prevent_initial_call=True,
        )
        def update_tag_panel_preview(record):
            if record is None:
                return html.Small("No cluster selected.", className="text-muted")
            cid = record.get("ID_UNIQUE_CLUSTER", "?")
            ra = record.get("RIGHT_ASCENSION_CLUSTER", "?")
            dec = record.get("DECLINATION_CLUSTER", "?")
            snr = record.get("SNR_CLUSTER", "?")
            z = record.get("Z_CLUSTER", "?")
            try:
                ra = f"{float(ra):.3f}°"
                dec = f"{float(dec):.3f}°"
                snr = f"{float(snr):.2f}"
                z = f"{float(z):.2f}"
            except (TypeError, ValueError):
                pass
            return html.Div([
                html.Span("Tagging: ", className="fw-bold text-warning me-1"),
                html.Span(f"ID {cid}", className="fw-bold me-2"),
                html.Span(f"RA {ra}  Dec {dec}", className="me-2 text-muted"),
                html.Span(f"SNR {snr}  z {z}", className="text-muted"),
            ])

        @self.app.callback(
            [
                Output("tagged-clusters-store", "data"),
                Output("tagged-clusters-summary", "children"),
                Output("status-info", "children", allow_duplicate=True),
            ],
            [Input("tab-tag-button", "n_clicks")],
            [
                State("tab-tag-value", "value"),
                State("tab-tag-dataset-label", "value"),
                State("selected-cluster-merged-record", "data"),
                State("tagged-clusters-store", "data"),
            ],
            prevent_initial_call=True,
        )
        def tag_selected_cluster(tag_clicks, selected_tag, dataset_label, selected_record, tagged_rows):
            """Tag currently selected merged cluster candidate as good/bad/dubious."""
            if not tag_clicks:
                return dash.no_update, dash.no_update, dash.no_update

            if selected_record is None:
                return (
                    dash.no_update,
                    dash.no_update,
                    dbc.Alert(
                        "⚠️ No merged cluster resolved for current click.",
                        color="warning",
                    ),
                )

            if selected_tag not in {"good", "bad", "dubious"}:
                return (
                    dash.no_update,
                    dash.no_update,
                    dbc.Alert("⚠️ Invalid tag. Choose good, bad, or dubious.", color="warning"),
                )

            tagged_rows = tagged_rows if isinstance(tagged_rows, list) else []
            updated_record = dict(selected_record)
            updated_record["cluster_tag"] = selected_tag
            updated_record["dataset_label"] = (dataset_label or "").strip().lower()
            updated_rows = self._upsert_tagged_rows(tagged_rows, updated_record)

            cluster_id = updated_record.get("ID_UNIQUE_CLUSTER", "unknown")
            return (
                updated_rows,
                self._build_tagged_summary(updated_rows),
                dbc.Alert(
                    f"🏷️ Tagged cluster {cluster_id} as '{selected_tag}'.",
                    color="success",
                ),
            )

        @self.app.callback(
            [
                Output("tagged-clusters-save-conflict-modal", "is_open"),
                Output("tagged-clusters-pending-save", "data"),
                Output("tagged-clusters-save-conflict-message", "children"),
                Output("status-info", "children", allow_duplicate=True),
            ],
            [
                Input("tab-save-tagged-clusters-button", "n_clicks"),
                Input("tagged-clusters-overwrite-button", "n_clicks"),
                Input("tagged-clusters-save-suffix-button", "n_clicks"),
                Input("tagged-clusters-append-button", "n_clicks"),
                Input("tagged-clusters-cancel-save-button", "n_clicks"),
            ],
            [
                State("tagged-clusters-output-path", "value"),
                State("tagged-clusters-store", "data"),
                State("tagged-clusters-pending-save", "data"),
            ],
            prevent_initial_call=True,
        )
        def save_tagged_clusters(
            save_clicks,
            overwrite_clicks,
            suffix_clicks,
            append_clicks,
            cancel_clicks,
            output_path,
            tagged_rows,
            pending_save,
        ):
            """Save tagged merged-catalog rows with overwrite/suffix/append behavior."""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update

            trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
            tagged_rows = tagged_rows if isinstance(tagged_rows, list) else []

            if trigger_id == "tab-save-tagged-clusters-button":
                if not tagged_rows:
                    return (
                        False,
                        None,
                        "",
                        dbc.Alert("⚠️ No tagged clusters to save.", color="warning"),
                    )

                resolved_path = os.path.expanduser((output_path or "").strip())
                if not resolved_path:
                    return (
                        False,
                        None,
                        "",
                        dbc.Alert("⚠️ Enter a valid CSV output path.", color="warning"),
                    )

                if os.path.exists(resolved_path):
                    return (
                        True,
                        {"path": resolved_path},
                        html.Small(f"Existing file: {resolved_path}", className="text-muted"),
                        dbc.Alert("⚠️ File exists. Choose overwrite, suffix, or append.", color="warning"),
                    )

                _, total_rows = self._write_tagged_rows_to_csv(
                    resolved_path, tagged_rows, mode="overwrite"
                )
                return (
                    False,
                    None,
                    "",
                    dbc.Alert(
                        f"✅ Saved {total_rows} tagged clusters to {resolved_path}",
                        color="success",
                    ),
                )

            if trigger_id == "tagged-clusters-cancel-save-button":
                return False, None, "", dbc.Alert("Save cancelled.", color="secondary")

            if trigger_id in {
                "tagged-clusters-overwrite-button",
                "tagged-clusters-save-suffix-button",
                "tagged-clusters-append-button",
            }:
                pending_path = (
                    pending_save.get("path")
                    if isinstance(pending_save, dict)
                    else os.path.expanduser((output_path or "").strip())
                )
                if not pending_path:
                    return (
                        False,
                        None,
                        "",
                        dbc.Alert("⚠️ Missing pending save path.", color="warning"),
                    )

                if trigger_id == "tagged-clusters-overwrite-button":
                    _, total_rows = self._write_tagged_rows_to_csv(
                        pending_path, tagged_rows, mode="overwrite"
                    )
                    return (
                        False,
                        None,
                        "",
                        dbc.Alert(
                            f"✅ Overwrote {pending_path} with {total_rows} tagged rows.",
                            color="success",
                        ),
                    )

                if trigger_id == "tagged-clusters-save-suffix-button":
                    suffixed_path = self._get_suffixed_output_path(pending_path)
                    _, total_rows = self._write_tagged_rows_to_csv(
                        suffixed_path, tagged_rows, mode="overwrite"
                    )
                    return (
                        False,
                        None,
                        "",
                        dbc.Alert(
                            f"✅ Saved {total_rows} tagged rows to {suffixed_path}",
                            color="success",
                        ),
                    )

                if trigger_id == "tagged-clusters-append-button":
                    appended_rows, total_rows = self._write_tagged_rows_to_csv(
                        pending_path, tagged_rows, mode="append"
                    )
                    return (
                        False,
                        None,
                        "",
                        dbc.Alert(
                            f"✅ Appended {appended_rows} rows into {pending_path} (total: {total_rows}).",
                            color="success",
                        ),
                    )

            return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    def _resolve_merged_record_for_click(
        self, point: Dict[str, Any], algorithm: str
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Resolve a clicked plot point to a row in data_detcluster_mergedcat."""
        try:
            data = self.data_loader.load_data(select_algorithm=algorithm)
        except Exception as exc:
            return None, f"Failed to load merged catalog: {exc}"

        merged_catalog = data.get("data_detcluster_mergedcat") if isinstance(data, dict) else None
        if merged_catalog is None or len(merged_catalog) == 0:
            return None, "Merged catalog unavailable."

        customdata = point.get("customdata", [])
        if not isinstance(customdata, (list, tuple, np.ndarray)):
            customdata = [customdata]

        if len(customdata) >= 4:
            by_id = self._find_merged_record_by_cluster_id(merged_catalog, customdata[3])
            if by_id is not None:
                return by_id, f"Resolved from ID_UNIQUE_CLUSTER={by_id.get('ID_UNIQUE_CLUSTER')}"

        record, distance_arcsec = self._match_merged_record_by_proximity(
            merged_catalog,
            ra=point.get("x"),
            dec=point.get("y"),
            snr=customdata[0] if len(customdata) > 0 else None,
            redshift=customdata[1] if len(customdata) > 1 else None,
            det_code=customdata[2] if len(customdata) > 2 else None,
        )
        if record is None:
            return None, "Could not resolve merged row for selected point."

        confidence = "high" if distance_arcsec <= 5.0 else "low"
        return (
            record,
            f"Resolved by nearest RA/Dec + SNR/z ({distance_arcsec:.2f} arcsec, confidence: {confidence}).",
        )

    def _find_merged_record_by_cluster_id(
        self, merged_catalog: np.ndarray, cluster_id: Any
    ) -> Optional[Dict[str, Any]]:
        """Find merged row by ID_UNIQUE_CLUSTER."""
        if "ID_UNIQUE_CLUSTER" not in merged_catalog.dtype.names:
            return None
        try:
            cluster_id_int = int(cluster_id)
        except (TypeError, ValueError):
            return None

        matches = merged_catalog[merged_catalog["ID_UNIQUE_CLUSTER"] == cluster_id_int]
        if len(matches) == 0:
            return None
        return self._structured_row_to_dict(matches[0])

    def _match_merged_record_by_proximity(
        self,
        merged_catalog: np.ndarray,
        ra: Any,
        dec: Any,
        snr: Any,
        redshift: Any,
        det_code: Any,
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """Match click coordinates to merged rows using RA/Dec and property tie-breakers."""
        try:
            ra_val = float(ra)
            dec_val = float(dec)
        except (TypeError, ValueError):
            return None, float("inf")

        candidates = merged_catalog
        if "DET_CODE_NB" in merged_catalog.dtype.names:
            try:
                det_code_int = int(det_code)
                det_filtered = merged_catalog[merged_catalog["DET_CODE_NB"] == det_code_int]
                if len(det_filtered) > 0:
                    candidates = det_filtered
            except (TypeError, ValueError):
                pass

        if len(candidates) == 0:
            return None, float("inf")

        ra_arr = np.asarray(candidates["RIGHT_ASCENSION_CLUSTER"], dtype=float)
        dec_arr = np.asarray(candidates["DECLINATION_CLUSTER"], dtype=float)
        dist_deg = np.sqrt((ra_arr - ra_val) ** 2 + (dec_arr - dec_val) ** 2)

        try:
            snr_val = float(snr)
            snr_diff = np.abs(np.asarray(candidates["SNR_CLUSTER"], dtype=float) - snr_val)
        except (TypeError, ValueError):
            snr_diff = np.zeros(len(candidates), dtype=float)

        try:
            z_val = float(redshift)
            z_diff = np.abs(np.asarray(candidates["Z_CLUSTER"], dtype=float) - z_val)
        except (TypeError, ValueError):
            z_diff = np.zeros(len(candidates), dtype=float)

        best_index = int(np.lexsort((z_diff, snr_diff, dist_deg))[0])
        best_row = candidates[best_index]
        return self._structured_row_to_dict(best_row), float(dist_deg[best_index] * 3600.0)

    def _structured_row_to_dict(self, row: Any) -> Dict[str, Any]:
        """Convert numpy structured-array row to plain Python dict."""
        row_dict: Dict[str, Any] = {}
        for field_name in row.dtype.names:
            value = row[field_name]
            if isinstance(value, np.generic):
                value = value.item()
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="ignore")
            row_dict[field_name] = value
        return row_dict

    def _record_identity(self, record: Dict[str, Any]) -> Tuple[Any, Any, Any, Any]:
        """Build identity key for upsert behavior in tagged cluster store."""
        if record.get("ID_UNIQUE_CLUSTER") is not None:
            return ("id", record.get("ID_UNIQUE_CLUSTER"), None, None)
        return (
            "coords",
            record.get("RIGHT_ASCENSION_CLUSTER"),
            record.get("DECLINATION_CLUSTER"),
            record.get("SNR_CLUSTER"),
        )

    def _upsert_tagged_rows(
        self, tagged_rows: List[Dict[str, Any]], updated_record: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Insert/replace tagged row by identity key."""
        target_key = self._record_identity(updated_record)
        updated_rows: List[Dict[str, Any]] = []
        replaced = False

        for row in tagged_rows:
            if self._record_identity(row) == target_key:
                updated_rows.append(updated_record)
                replaced = True
            else:
                updated_rows.append(row)

        if not replaced:
            updated_rows.append(updated_record)
        return updated_rows

    def _build_tagged_summary(self, tagged_rows: List[Dict[str, Any]]):
        """Build summary UI for current tagged rows in session."""
        if not tagged_rows:
            return html.Small("No tagged clusters yet.", className="text-muted")

        counts = {"good": 0, "bad": 0, "dubious": 0}
        for row in tagged_rows:
            tag_value = row.get("cluster_tag")
            if tag_value in counts:
                counts[tag_value] += 1

        return html.Div(
            [
                html.Strong(f"Tagged clusters: {len(tagged_rows)}"),
                html.Div(
                    f"good={counts['good']}, bad={counts['bad']}, dubious={counts['dubious']}",
                    className="small text-muted",
                ),
            ]
        )

    def _reorder_tag_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """Place cluster_tag and dataset_label immediately after ID_UNIQUE_CLUSTER when present."""
        df = df.copy()
        if "cluster_tag" not in df.columns:
            df["cluster_tag"] = ""
        if "dataset_label" not in df.columns:
            df["dataset_label"] = ""

        tag_cols = ["cluster_tag", "dataset_label"]
        cols = [col for col in df.columns if col not in tag_cols]
        if "ID_UNIQUE_CLUSTER" in cols:
            insert_at = cols.index("ID_UNIQUE_CLUSTER") + 1
            for i, tc in enumerate(tag_cols):
                cols.insert(insert_at + i, tc)
        else:
            cols.extend(tag_cols)
        return df[cols]

    def _rows_to_tagged_dataframe(self, tagged_rows: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert tagged row dictionaries to dataframe with required column order."""
        if not tagged_rows:
            return pd.DataFrame()
        df = pd.DataFrame(tagged_rows)
        return self._reorder_tag_column(df)

    def _merge_tagged_dataframes(self, existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """Append new tagged rows, replacing duplicates by (ID_UNIQUE_CLUSTER, dataset_label)."""
        existing_df = self._reorder_tag_column(existing_df)
        new_df = self._reorder_tag_column(new_df)

        all_cols: List[str] = list(existing_df.columns)
        for col in new_df.columns:
            if col not in all_cols:
                all_cols.append(col)

        existing_df = existing_df.reindex(columns=all_cols)
        new_df = new_df.reindex(columns=all_cols)

        has_id = "ID_UNIQUE_CLUSTER" in existing_df.columns and "ID_UNIQUE_CLUSTER" in new_df.columns
        has_label = "dataset_label" in existing_df.columns and "dataset_label" in new_df.columns

        if has_id:
            existing_ids = pd.to_numeric(existing_df["ID_UNIQUE_CLUSTER"], errors="coerce")
            new_ids = pd.to_numeric(new_df["ID_UNIQUE_CLUSTER"], errors="coerce")

            if has_label:
                new_keys = set(
                    zip(new_ids.dropna().astype(int), new_df.loc[new_ids.notna(), "dataset_label"].fillna(""))
                )
                existing_keys = list(
                    zip(existing_ids.fillna(-1).astype(int), existing_df["dataset_label"].fillna(""))
                )
                keep_mask = [key not in new_keys for key in existing_keys]
                existing_df = existing_df[keep_mask]
            else:
                existing_df = existing_df[~existing_ids.isin(new_ids.dropna())]

        merged_df = pd.concat([existing_df, new_df], ignore_index=True)
        return self._reorder_tag_column(merged_df)

    def _get_suffixed_output_path(self, output_path: str) -> str:
        """Generate next available suffixed output path."""
        root, ext = os.path.splitext(output_path)
        if not ext:
            ext = ".csv"
        suffix = 1
        while True:
            candidate = f"{root}_{suffix}{ext}"
            if not os.path.exists(candidate):
                return candidate
            suffix += 1

    def _write_tagged_rows_to_csv(
        self, output_path: str, tagged_rows: List[Dict[str, Any]], mode: str
    ) -> Tuple[int, int]:
        """Write tagged rows to CSV and return (written_rows, final_total_rows)."""
        tagged_df = self._rows_to_tagged_dataframe(tagged_rows)
        if tagged_df.empty:
            return 0, 0

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        if mode == "append" and os.path.exists(output_path):
            existing_df = pd.read_csv(output_path)
            merged_df = self._merge_tagged_dataframes(existing_df, tagged_df)
            merged_df.to_csv(output_path, index=False)
            return len(tagged_df), len(merged_df)

        tagged_df.to_csv(output_path, index=False)
        return len(tagged_df), len(tagged_df)

    def _extract_existing_catred_traces(self, current_figure):
        """Extract existing CATRED traces from current figure"""
        existing_catred_traces = []
        if current_figure and "data" in current_figure:
            for trace in current_figure["data"]:
                trace_name = ""
                if isinstance(trace, dict):
                    trace_name = trace.get("name", "")
                elif hasattr(trace, "name"):
                    trace_name = trace.name or ""

                if trace_name and trace_name.startswith("CATRED"):
                    if isinstance(trace, dict):
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
                    else:
                        existing_catred_traces.append(trace)
                    print(f"Debug: Preserved existing CATRED trace: {trace_name}")
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
                        or "Inverted mask overlay" in trace["name"]
                        or trace["name"] == "Mask Colorbar"
                    )
                ):
                    # Preserve the original trace type (Image, Heatmap, etc.)
                    trace_type = trace.get("type", "scatter")

                    if trace_type == "scatter":
                        if trace.get("name") == "Mask Colorbar":
                            # Preserve marker config for colorbar-only scatter traces.
                            existing_trace = go.Scatter(
                                x=trace.get("x"),
                                y=trace.get("y"),
                                mode=trace.get("mode", "markers"),
                                marker=trace.get("marker", {}),
                                showlegend=trace.get("showlegend", False),
                                hoverinfo=trace.get("hoverinfo", "skip"),
                                name=trace.get("name", "Mask Colorbar"),
                            )
                        else:
                            existing_trace = go.Scatter(
                                x=trace.get("x"),
                                y=trace.get("y"),
                                mode=trace.get("mode", "lines"),
                                fill=trace.get("fill", "toself"),
                                fillcolor=trace.get("fillcolor", "rgba(0,0,0,0)"),
                                line=trace.get("line", {}),
                                name=trace.get("name", "Mask overlay"),
                                showlegend=trace.get("showlegend", False),
                                hoverinfo=trace.get("hoverinfo", "skip"),
                                opacity=trace.get("opacity", 1.0),
                            )
                    elif trace_type == "image":
                        existing_trace = go.Image(
                            source=trace.get("source"),
                            x0=trace.get("x0"),
                            y0=trace.get("y0"),
                            dx=trace.get("dx"),
                            dy=trace.get("dy"),
                            name=trace.get("name", "Mask overlay"),
                            opacity=trace.get("opacity", 1.0),
                            layer=trace.get("layer", "below"),
                        )
                    elif trace_type == "heatmap":
                        existing_trace = go.Heatmap(
                            z=trace.get("z"),
                            x=trace.get("x"),
                            y=trace.get("y"),
                            name=trace.get("name", "Mask overlay"),
                            opacity=trace.get("opacity", 1.0),
                            colorscale=trace.get("colorscale", "gray"),
                            showscale=trace.get("showscale", False),
                        )
                    else:
                        # Keep original trace as-is for unknown types
                        existing_trace = trace

                    existing_mask_overlay_traces.append(existing_trace)
                    print(
                        f"Debug: Preserved existing mask overlay trace: {trace['name']} (type: {trace_type})"
                    )
        return existing_mask_overlay_traces

    def _extract_existing_members_traces(self, current_figure):
        """Extract existing Members traces from current figure to preserve them across rebuilds."""
        result = []
        if current_figure and "data" in current_figure:
            for trace in current_figure["data"]:
                name = trace.get("name", "") if isinstance(trace, dict) else getattr(trace, "name", "") or ""
                if name.startswith("Members (ID"):
                    result.append(trace)
                    print(f"Debug: Preserved existing Members trace: {name}")
        return result

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

    def _create_empty_phz_plot(self, message="Click on a CATRED data point to view its PHZ_PDF"):
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

    def _preserve_zoom_state_fallback(self, fig, relayout_data):
        """Fallback zoom state preservation method"""
        if relayout_data:
            if "xaxis.range[0]" in relayout_data and "xaxis.range[1]" in relayout_data:
                fig.update_xaxes(
                    range=[relayout_data["xaxis.range[0]"], relayout_data["xaxis.range[1]"]],
                    autorange=False,
                )
            elif "xaxis.range" in relayout_data:
                fig.update_xaxes(range=relayout_data["xaxis.range"], autorange=False)

            if "yaxis.range[0]" in relayout_data and "yaxis.range[1]" in relayout_data:
                fig.update_yaxes(
                    range=[relayout_data["yaxis.range[0]"], relayout_data["yaxis.range[1]"]]
                )
            elif "yaxis.range" in relayout_data:
                fig.update_yaxes(range=relayout_data["yaxis.range"])

    def _setup_parameter_sync_callbacks(self):
        """Setup callbacks to sync parameters between tab inputs and sliders"""

        # Bidirectional sync for magnitude limit
        @self.app.callback(
            [
                Output("magnitude-limit-slider", "value", allow_duplicate=True),
                Output("tab-catred-maglim", "value", allow_duplicate=True),
            ],
            [Input("magnitude-limit-slider", "value"), Input("tab-catred-maglim", "value")],
            prevent_initial_call=True,
        )
        def sync_magnitude_limit_bidirectional(slider_value, tab_value):
            """Bidirectionally sync magnitude limit between slider and tab input"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update

            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if triggered_id == "magnitude-limit-slider" and slider_value is not None:
                # Slider changed, update tab input
                return dash.no_update, slider_value
            elif triggered_id == "tab-catred-maglim" and tab_value is not None:
                # Tab input changed, update slider
                return tab_value, dash.no_update

            return dash.no_update, dash.no_update

        # Bidirectional sync for threshold
        @self.app.callback(
            Output("tab-catred-mask-threshold", "value", allow_duplicate=True),
            [Input("catred-threshold-slider", "value")],
            prevent_initial_call=True,
        )
        def sync_threshold_slider_to_tab(slider_value):
            """Update tab input when threshold slider changes"""
            if slider_value is not None:
                return slider_value
            return dash.no_update

        @self.app.callback(
            Output("catred-threshold-slider", "value", allow_duplicate=True),
            [Input("tab-catred-mask-threshold", "value")],
            prevent_initial_call=True,
        )
        def sync_threshold_tab_to_slider(tab_value):
            """Update threshold slider when tab input changes"""
            if tab_value is not None:
                return tab_value
            return dash.no_update

    def _setup_trace_management_callbacks(self):
        """Setup callbacks for managing cluster modal traces (visibility and clear)"""

        # Mosaic Cutout visibility toggle
        @self.app.callback(
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-cutout-toggle-visibility", "children"),
                Output("tab-cutout-toggle-visibility", "disabled"),
            ],
            [Input("tab-cutout-toggle-visibility", "n_clicks")],
            [State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )
        def toggle_cutout_visibility(n_clicks, current_figure):
            """Toggle visibility of mosaic cutout traces"""
            if not current_figure or "data" not in current_figure:
                return dash.no_update, dash.no_update, dash.no_update

            # Find cutout traces
            cutout_traces_exist = False
            all_cutouts_visible = True

            for trace in current_figure["data"]:
                trace_name = trace.get("name", "")
                if "MER-Mosaic cutout" in trace_name:
                    cutout_traces_exist = True
                    if trace.get("visible", True) == False or trace.get("visible") == "legendonly":
                        all_cutouts_visible = False

            if not cutout_traces_exist:
                return dash.no_update, dash.no_update, True

            # Toggle visibility
            new_visibility = False if all_cutouts_visible else True

            for trace in current_figure["data"]:
                trace_name = trace.get("name", "")
                if "MER-Mosaic cutout" in trace_name:
                    trace["visible"] = new_visibility

            # Update button text
            button_text = [
                html.I(className="fas fa-eye me-1"),
                "Hide" if new_visibility else "Show",
            ]

            return current_figure, button_text, False

        # Mosaic Cutout clear (clientside)
        self.app.clientside_callback(
            """
            function(n_clicks, figure) {
                if (!n_clicks) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
                }
                if (!figure || !figure.data) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
                }

                const filtered = (figure.data || []).filter(function(trace) {
                    const name = (trace && trace.name) ? trace.name : '';
                    return name.indexOf('MER-Mosaic cutout') < 0;
                });

                const newFigure = Object.assign({}, figure, {data: filtered});
                return [newFigure, true, true];
            }
            """,
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-cutout-toggle-visibility", "disabled", allow_duplicate=True),
                Output("tab-cutout-clear", "disabled"),
            ],
            Input("tab-cutout-clear", "n_clicks"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

        # CATRED Box visibility toggle
        @self.app.callback(
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-catred-box-toggle-visibility", "children"),
                Output("tab-catred-box-toggle-visibility", "disabled"),
            ],
            [Input("tab-catred-box-toggle-visibility", "n_clicks")],
            [State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )
        def toggle_catred_box_visibility(n_clicks, current_figure):
            """Toggle visibility of CATRED box traces"""
            if not current_figure or "data" not in current_figure:
                return dash.no_update, dash.no_update, dash.no_update

            # Find CATRED box traces
            catred_box_traces_exist = False
            all_boxes_visible = True

            for trace in current_figure["data"]:
                trace_name = trace.get("name", "")
                if "CATRED" in trace_name and "Boxed" in trace_name:
                    catred_box_traces_exist = True
                    if trace.get("visible", True) == False or trace.get("visible") == "legendonly":
                        all_boxes_visible = False

            if not catred_box_traces_exist:
                return dash.no_update, dash.no_update, True

            # Toggle visibility
            new_visibility = False if all_boxes_visible else True

            for trace in current_figure["data"]:
                trace_name = trace.get("name", "")
                if "CATRED" in trace_name and "Boxed" in trace_name:
                    trace["visible"] = new_visibility

            # Update button text
            button_text = [
                html.I(className="fas fa-eye me-1"),
                "Hide" if new_visibility else "Show",
            ]

            return current_figure, button_text, False

        # CATRED Box clear (clientside)
        self.app.clientside_callback(
            """
            function(n_clicks, figure) {
                if (!n_clicks) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
                }
                if (!figure || !figure.data) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
                }

                const filtered = (figure.data || []).filter(function(trace) {
                    const name = (trace && trace.name) ? trace.name : '';
                    if (name.indexOf('CATRED') >= 0 && name.indexOf('Boxed') >= 0) return false;
                    if (name.indexOf('in CATRED region') >= 0) return false;
                    if (name.indexOf('near CATRED') >= 0 && name.indexOf('clusters') < 0) return false;
                    return true;
                });

                const newFigure = Object.assign({}, figure, {data: filtered});
                return [newFigure, true, true];
            }
            """,
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-catred-box-toggle-visibility", "disabled", allow_duplicate=True),
                Output("tab-catred-box-clear", "disabled"),
            ],
            Input("tab-catred-box-clear", "n_clicks"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

        @self.app.callback(
            Output("tab-catred-box-clear", "title"),
            Input("tab-catred-box-clear", "n_clicks"),
            prevent_initial_call=True,
        )
        def clear_catred_box_server_state(n_clicks):
            """Clear cached CATRED state when the box overlay is removed."""
            if not n_clicks:
                return dash.no_update

            if self.catred_handler:
                self.catred_handler.clear_traces_cache()
                self.catred_handler.current_catred_data = None

            if self.trace_creator:
                self.trace_creator.clear_catred_data()

            print(f"Debug: CATRED box server state cleared (click #{n_clicks})")
            return dash.no_update

        # Mask Cutout visibility toggle
        @self.app.callback(
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-mask-cutout-toggle-visibility", "children"),
                Output("tab-mask-cutout-toggle-visibility", "disabled"),
            ],
            [Input("tab-mask-cutout-toggle-visibility", "n_clicks")],
            [State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )
        def toggle_mask_cutout_visibility(n_clicks, current_figure):
            """Toggle visibility of mask cutout traces"""
            if not current_figure or "data" not in current_figure:
                return dash.no_update, dash.no_update, dash.no_update

            # Find mask cutout traces
            mask_cutout_traces_exist = False
            all_masks_visible = True

            for trace in current_figure["data"]:
                trace_name = trace.get("name", "")
                if "Mask overlay (cutout)" in trace_name or "Mask Colorbar" in trace_name:
                    mask_cutout_traces_exist = True
                    if trace.get("visible", True) == False or trace.get("visible") == "legendonly":
                        all_masks_visible = False

            if not mask_cutout_traces_exist:
                return dash.no_update, dash.no_update, True

            # Toggle visibility
            new_visibility = False if all_masks_visible else True

            for trace in current_figure["data"]:
                trace_name = trace.get("name", "")
                if "Mask overlay (cutout)" in trace_name or "Mask Colorbar" in trace_name:
                    trace["visible"] = new_visibility

            # Update button text
            button_text = [
                html.I(className="fas fa-eye me-1"),
                "Hide" if new_visibility else "Show",
            ]

            return current_figure, button_text, False

        # Mask Cutout clear (clientside)
        self.app.clientside_callback(
            """
            function(n_clicks, figure) {
                if (!n_clicks) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
                }
                if (!figure || !figure.data) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
                }

                const filtered = (figure.data || []).filter(function(trace) {
                    const name = (trace && trace.name) ? trace.name : '';
                    return !(name.indexOf('Mask overlay (cutout)') >= 0 || name.indexOf('Mask Colorbar') >= 0);
                });

                const newFigure = Object.assign({}, figure, {data: filtered});
                return [newFigure, true, true];
            }
            """,
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-mask-cutout-toggle-visibility", "disabled", allow_duplicate=True),
                Output("tab-mask-cutout-clear", "disabled"),
            ],
            Input("tab-mask-cutout-clear", "n_clicks"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

        # Members clear (clientside)
        self.app.clientside_callback(
            """
            function(n_clicks, figure) {
                if (!n_clicks) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
                }
                if (!figure || !figure.data) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
                }

                const filtered = (figure.data || []).filter(function(trace) {
                    const name = (trace && trace.name) ? trace.name : '';
                    return name.indexOf('Members (ID') < 0;
                });

                const radiusColors = new Set(['#FF8C00', '#00BFFF']);
                const filteredShapes = ((figure.layout || {}).shapes || []).filter(function(s) {
                    return !(s.type === 'circle' && s.line && radiusColors.has(s.line.color));
                });
                const newLayout = Object.assign({}, figure.layout, {shapes: filteredShapes});
                const newFigure = Object.assign({}, figure, {data: filtered, layout: newLayout});
                return [newFigure, true, true];
            }
            """,
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-members-toggle-visibility", "disabled", allow_duplicate=True),
                Output("tab-members-clear", "disabled", allow_duplicate=True),
            ],
            Input("tab-members-clear", "n_clicks"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

        @self.app.callback(
            Output("tab-members-clear", "title"),
            Input("tab-members-clear", "n_clicks"),
            prevent_initial_call=True,
        )
        def clear_members_server_state(n_clicks):
            if not n_clicks:
                return dash.no_update
            if self.catred_handler and self.catred_handler.current_catred_data:
                keys_to_remove = [k for k in self.catred_handler.current_catred_data if k.startswith("Members (ID")]
                for k in keys_to_remove:
                    del self.catred_handler.current_catred_data[k]
                print(f"Debug: Cleared {len(keys_to_remove)} Members entry(ies) from current_catred_data")
            return dash.no_update

        # Members visibility toggle
        @self.app.callback(
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-members-toggle-visibility", "children"),
                Output("tab-members-toggle-visibility", "disabled", allow_duplicate=True),
            ],
            [Input("tab-members-toggle-visibility", "n_clicks")],
            [State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )
        def toggle_members_visibility(n_clicks, current_figure):
            if not current_figure or "data" not in current_figure:
                return dash.no_update, dash.no_update, dash.no_update

            members_exist = False
            all_visible = True

            for trace in current_figure["data"]:
                trace_name = trace.get("name", "")
                if "Members (ID" in trace_name:
                    members_exist = True
                    if trace.get("visible", True) in (False, "legendonly"):
                        all_visible = False

            if not members_exist:
                return dash.no_update, dash.no_update, dash.no_update

            new_visible = not all_visible
            new_data = []
            for trace in current_figure["data"]:
                if "Members (ID" in trace.get("name", ""):
                    updated = dict(trace)
                    updated["visible"] = new_visible
                    new_data.append(updated)
                else:
                    new_data.append(trace)

            updated_figure = dict(current_figure)
            updated_figure["data"] = new_data
            button_label = [html.I(className="fas fa-eye-slash me-2"), "Show"] if all_visible else [html.I(className="fas fa-eye me-2"), "Hide"]
            return updated_figure, button_label, False

        # Enable buttons when traces are generated
        @self.app.callback(
            [
                Output("tab-cutout-toggle-visibility", "disabled", allow_duplicate=True),
                Output("tab-cutout-clear", "disabled", allow_duplicate=True),
                Output("tab-catred-box-toggle-visibility", "disabled", allow_duplicate=True),
                Output("tab-catred-box-clear", "disabled", allow_duplicate=True),
                Output("tab-mask-cutout-toggle-visibility", "disabled", allow_duplicate=True),
                Output("tab-mask-cutout-clear", "disabled", allow_duplicate=True),
            ],
            [Input("cluster-plot", "figure")],
            prevent_initial_call=True,
        )
        def enable_trace_buttons(current_figure):
            """Enable/disable trace management buttons based on trace existence"""
            if not current_figure or "data" not in current_figure:
                return True, True, True, True, True, True

            has_cutouts = False
            has_catred_boxes = False
            has_mask_cutouts = False

            for trace in current_figure["data"]:
                trace_name = trace.get("name", "")
                if "MER-Mosaic cutout" in trace_name:
                    has_cutouts = True
                if "CATRED" in trace_name and "Boxed" in trace_name:
                    has_catred_boxes = True
                if "Mask overlay (cutout)" in trace_name:
                    has_mask_cutouts = True

            return (
                not has_cutouts,
                not has_cutouts,  # cutout buttons
                not has_catred_boxes,
                not has_catred_boxes,  # CATRED box buttons
                not has_mask_cutouts,
                not has_mask_cutouts,  # mask cutout buttons
            )

    def _fetch_member_radec(self, member_object_ids, data, matched=None):
        """Look up RA/DEC, PHZ and PMEM columns for member galaxy OBJECT_IDs from nearby CATRED FITS tiles.

        Returns (ra, dec, phz_pdf, phz_mode_1, phz_median, phz_70_int, pmem_zp, pmem_rs).
        May be shorter than input if some IDs are not found in the searched tiles.
        """
        from astropy.io import fits as _fits

        _empty = (np.array([]), np.array([]), [], [], [], [], [], [])

        if not self.selected_cluster:
            return _empty

        catred_info = data.get("catred_info")
        catred_dsr = data.get("catred_dsr")
        if catred_info is None or catred_info.empty or not self.catred_handler:
            return _empty

        ra_center = self.selected_cluster["ra"]
        dec_center = self.selected_cluster["dec"]
        half_deg = 0.5
        ra_min = ra_center - half_deg
        ra_max = ra_center + half_deg
        dec_min = dec_center - half_deg
        dec_max = dec_center + half_deg

        tile_ids = self.catred_handler._find_intersecting_tiles(data, ra_min, ra_max, dec_min, dec_max)
        if not tile_ids:
            return _empty

        # Build OBJECT_ID → (PMEM_ZP, PMEM_RS) lookup from members catalog row
        pmem_lookup = {}
        if matched is not None and len(matched) > 0:
            names = matched.dtype.names or []
            has_zp = "PMEM_ZP" in names
            has_rs = "PMEM_RS" in names
            for row in matched:
                oid = int(row["OBJECT_ID"])
                pmem_lookup[oid] = (
                    float(row["PMEM_ZP"]) if has_zp else float("nan"),
                    float(row["PMEM_RS"]) if has_rs else float("nan"),
                )

        member_ids_arr = np.asarray(member_object_ids)
        remaining = set(member_ids_arr.tolist())
        ra_all, dec_all = [], []
        phz_pdf_all, phz_mode1_all, phz_median_all, phz_70int_all = [], [], [], []
        pmem_zp_all, pmem_rs_all = [], []

        for tile_id in tile_ids:
            if not remaining:
                break
            rows = catred_info.loc[
                (catred_info["mertileid"] == tile_id)
                & (catred_info["dataset_release"] == catred_dsr)
            ]
            if rows.empty:
                continue
            fits_file = rows.iloc[0]["fits_file"]
            try:
                with _fits.open(fits_file, mode="readonly", memmap=True) as hdul:
                    tdata = hdul[1].data
                    if "OBJECT_ID" not in tdata.names:
                        continue
                    obj_ids = tdata["OBJECT_ID"]
                    mask = np.isin(obj_ids, member_ids_arr)
                    if not np.any(mask):
                        continue
                    n_match = int(np.sum(mask))
                    ra_all.append(tdata["RIGHT_ASCENSION"][mask])
                    dec_all.append(tdata["DECLINATION"][mask])
                    phz_pdf_all.extend(
                        tdata["PHZ_PDF"][mask].tolist() if "PHZ_PDF" in tdata.names
                        else [None] * n_match
                    )
                    phz_mode1_all.extend(
                        tdata["PHZ_MODE_1"][mask].tolist() if "PHZ_MODE_1" in tdata.names
                        else [float("nan")] * n_match
                    )
                    phz_median_all.extend(
                        tdata["PHZ_MEDIAN"][mask].tolist() if "PHZ_MEDIAN" in tdata.names
                        else [float("nan")] * n_match
                    )
                    phz_70int_all.extend(
                        tdata["PHZ_70_INT"][mask].tolist() if "PHZ_70_INT" in tdata.names
                        else [None] * n_match
                    )
                    found_ids = obj_ids[mask].tolist()
                    for oid in found_ids:
                        zp, rs = pmem_lookup.get(int(oid), (float("nan"), float("nan")))
                        pmem_zp_all.append(zp)
                        pmem_rs_all.append(rs)
                    remaining -= set(found_ids)
            except Exception as exc:
                print(f"Warning: could not read CATRED tile {tile_id} for member lookup: {exc}")

        if not ra_all:
            return _empty
        return (
            np.concatenate(ra_all),
            np.concatenate(dec_all),
            phz_pdf_all,
            phz_mode1_all,
            phz_median_all,
            phz_70int_all,
            pmem_zp_all,
            pmem_rs_all,
        )

    def _build_members_trace(self, ra, dec, cluster_id, color="#000000", size=10,
                             pmem_zp=None, pmem_rs=None):
        """Build a Scattergl trace for member galaxies."""
        n = len(ra)
        zp = pmem_zp if pmem_zp is not None and len(pmem_zp) == n else [float("nan")] * n
        rs = pmem_rs if pmem_rs is not None and len(pmem_rs) == n else [float("nan")] * n

        def _fmt(v):
            try:
                return "N/A" if v != v else f"{v:.3f}"  # v != v → isnan
            except Exception:
                return "N/A"

        customdata = [[_fmt(z), _fmt(r)] for z, r in zip(zp, rs)]
        return go.Scattergl(
            x=ra.tolist(),
            y=dec.tolist(),
            mode="markers",
            marker=dict(symbol="diamond-wide-open", size=size, color=color, line=dict(width=1.5, color=color)),
            name=f"Members (ID {int(cluster_id)})",
            customdata=customdata,
            hovertemplate=(
                "RA: %{x:.4f}<br>"
                "Dec: %{y:.4f}<br>"
                "PMEM ZP: %{customdata[0]}<br>"
                "PMEM RS: %{customdata[1]}<br>"
                "<extra></extra>"
            ),
        )

    def _build_radius_shapes(self, existing_shapes):
        """Return updated shapes list: preserve non-radius shapes, add RADIUS_ZP/RS circles."""
        import math
        rec = (self.selected_cluster or {}).get("merged_record") if self.selected_cluster else None
        ra = (self.selected_cluster or {}).get("ra") if self.selected_cluster else None
        dec = (self.selected_cluster or {}).get("dec") if self.selected_cluster else None

        # Strip old radius circles (identified by their colors)
        radius_colors = {"#FF8C00", "#00BFFF"}
        base = [s for s in (existing_shapes or [])
                if not (s.get("type") == "circle" and s.get("line", {}).get("color") in radius_colors)]

        if rec is None or ra is None or dec is None:
            return base

        cos_dec = math.cos(math.radians(float(dec))) or 1.0
        for key, color in [("RADIUS_ZP", "#FF8C00"), ("RADIUS_RS", "#00BFFF")]:
            v = rec.get(key)
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv != fv or fv <= 0:  # isnan or non-positive
                continue
            r_deg = fv / 60.0
            base.append(dict(
                type="circle", xref="x", yref="y",
                x0=ra - r_deg / cos_dec, x1=ra + r_deg / cos_dec,
                y0=dec - r_deg, y1=dec + r_deg,
                line=dict(color=color, width=1.5, dash="dash"),
                fillcolor="rgba(0,0,0,0)",
                layer="above",
            ))
        return base

    def _setup_cluster_members_callback(self):
        """Setup callbacks for Cluster Members buttons in modal and tab."""

        def _query_members(algorithm):
            """Return (matched_array, data_dict, error_msg_or_None)."""
            if not self.selected_cluster:
                return None, None, "No cluster selected."
            cluster_id = self.selected_cluster.get("merged_cluster_id")
            if cluster_id is None:
                return None, None, "Cluster ID not resolved for selected point."
            try:
                data = self.data_loader.load_data(select_algorithm=algorithm)
            except Exception as exc:
                return None, None, f"Failed to load data: {exc}"
            members = data.get("data_gluematchcat_members")
            if members is None:
                return None, None, "Members catalog not available. Set gluematchcat_members in config.ini."
            if "ID_UNIQUE_CLUSTER" not in members.dtype.names:
                return None, None, "Members catalog missing ID_UNIQUE_CLUSTER column."
            try:
                matched = members[members["ID_UNIQUE_CLUSTER"] == int(cluster_id)]
            except (TypeError, ValueError) as exc:
                return None, None, f"Invalid cluster ID: {exc}"
            return matched, data, None

        def _members_alert(n_table, n_plotted, cluster_id):
            content = [
                html.Div([
                    html.Span("In catalog: ", className="fw-bold"),
                    html.Span(f"{n_table} {'galaxy' if n_table == 1 else 'galaxies'}"),
                ]),
                html.Div([
                    html.Span("Plotted: ", className="fw-bold"),
                    html.Span(f"{n_plotted}"),
                    html.Span(
                        " (some may fall outside available CATRED tiles)" if n_plotted < n_table else "",
                        className="text-muted small ms-1",
                    ),
                ]),
            ]
            return dbc.Alert(
                [html.Strong(f"Cluster ID {int(cluster_id)} — "), *content],
                color="success" if n_table > 0 else "info",
                className="py-2",
            )

        @self.app.callback(
            [
                Output("cluster-members-output", "children"),
                Output("cluster-members-collapse", "is_open"),
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-members-toggle-visibility", "disabled", allow_duplicate=True),
                Output("tab-members-clear", "disabled", allow_duplicate=True),
                Output("tab-members-apply-filter", "disabled", allow_duplicate=True),
            ],
            [Input("cluster-members-button", "n_clicks")],
            [State("algorithm-dropdown", "value"), State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )
        def show_cluster_members(n_clicks, algorithm, current_figure):
            if not n_clicks:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
            matched, data, err = _query_members(algorithm)
            if err:
                return dbc.Alert(err, color="warning"), True, dash.no_update, dash.no_update, dash.no_update, dash.no_update
            cluster_id = self.selected_cluster["merged_cluster_id"]
            n_table = len(matched)
            if n_table == 0 or "OBJECT_ID" not in matched.dtype.names:
                return _members_alert(n_table, 0, cluster_id), True, dash.no_update, dash.no_update, dash.no_update, dash.no_update
            ra, dec, phz_pdf, phz_mode1, phz_median, phz_70int, pmem_zp, pmem_rs = self._fetch_member_radec(matched["OBJECT_ID"], data, matched=matched)
            n_plotted = len(ra)
            alert = _members_alert(n_table, n_plotted, cluster_id)
            if n_plotted == 0:
                return alert, True, dash.no_update, dash.no_update, dash.no_update, dash.no_update
            trace_name = f"Members (ID {int(cluster_id)})"
            if self.catred_handler:
                if self.catred_handler.current_catred_data is None:
                    self.catred_handler.current_catred_data = {}
                self.catred_handler.current_catred_data[trace_name] = {
                    "ra": ra.tolist(), "dec": dec.tolist(),
                    "phz_pdf": phz_pdf, "phz_mode_1": phz_mode1,
                    "phz_median": phz_median, "phz_70_int": phz_70int,
                    "pmem_zp": list(pmem_zp),
                    "pmem_rs": list(pmem_rs),
                }
            fig = go.Figure(current_figure)
            fig.add_trace(self._build_members_trace(ra, dec, cluster_id, pmem_zp=pmem_zp, pmem_rs=pmem_rs))
            existing_shapes = (current_figure or {}).get("layout", {}).get("shapes") or []
            fig.update_layout(shapes=self._build_radius_shapes(existing_shapes))
            return alert, True, fig.to_dict(), False, False, False

        @self.app.callback(
            [
                Output("tab-cluster-members-output", "children"),
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-members-toggle-visibility", "disabled", allow_duplicate=True),
                Output("tab-members-clear", "disabled", allow_duplicate=True),
                Output("tab-members-apply-filter", "disabled", allow_duplicate=True),
            ],
            [Input("tab-view-cluster-members", "n_clicks")],
            [
                State("algorithm-dropdown", "value"),
                State("cluster-plot", "figure"),
                State("tab-members-marker-color-picker", "value"),
                State("tab-members-marker-size", "value"),
                State("tab-members-filter-mode", "value"),
                State("tab-members-pmem-slider", "value"),
            ],
            prevent_initial_call=True,
        )
        def show_tab_cluster_members(n_clicks, algorithm, current_figure, marker_color, marker_size,
                                     filter_mode, pmem_threshold):
            if not n_clicks:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
            matched, data, err = _query_members(algorithm)
            if err:
                return dbc.Alert(err, color="warning"), dash.no_update, dash.no_update, dash.no_update, dash.no_update
            cluster_id = self.selected_cluster["merged_cluster_id"]
            n_table = len(matched)
            if n_table == 0 or "OBJECT_ID" not in matched.dtype.names:
                return _members_alert(n_table, 0, cluster_id), dash.no_update, dash.no_update, dash.no_update, dash.no_update
            ra, dec, phz_pdf, phz_mode1, phz_median, phz_70int, pmem_zp, pmem_rs = self._fetch_member_radec(matched["OBJECT_ID"], data, matched=matched)
            trace_name = f"Members (ID {int(cluster_id)})"
            if self.catred_handler:
                if self.catred_handler.current_catred_data is None:
                    self.catred_handler.current_catred_data = {}
                self.catred_handler.current_catred_data[trace_name] = {
                    "ra": ra.tolist(), "dec": dec.tolist(),
                    "phz_pdf": phz_pdf, "phz_mode_1": phz_mode1,
                    "phz_median": phz_median, "phz_70_int": phz_70int,
                    "pmem_zp": list(pmem_zp),
                    "pmem_rs": list(pmem_rs),
                }
            # Apply PMEM filter
            if filter_mode in ("zp", "rs") and pmem_threshold is not None:
                pmem_vals = pmem_zp if filter_mode == "zp" else pmem_rs
                keep = np.array([
                    i for i, v in enumerate(pmem_vals)
                    if not (v != v) and v > pmem_threshold
                ], dtype=int)
                if len(keep) > 0:
                    ra = ra[keep]
                    dec = dec[keep]
                    pmem_zp = [pmem_zp[i] for i in keep]
                    pmem_rs = [pmem_rs[i] for i in keep]
                    phz_pdf = [phz_pdf[i] for i in keep]
                    phz_mode1 = [phz_mode1[i] for i in keep]
                    phz_median = [phz_median[i] for i in keep]
                    phz_70int = [phz_70int[i] for i in keep]
                else:
                    ra = np.array([])
            n_plotted = len(ra)
            alert = _members_alert(n_table, n_plotted, cluster_id)
            if n_plotted == 0:
                return alert, dash.no_update, dash.no_update, dash.no_update, dash.no_update
            color = marker_color or "#000000"
            size = float(marker_size) if marker_size else 10.0
            fig = go.Figure(current_figure)
            fig.add_trace(self._build_members_trace(ra, dec, cluster_id, color=color, size=size, pmem_zp=pmem_zp, pmem_rs=pmem_rs))
            existing_shapes = (current_figure or {}).get("layout", {}).get("shapes") or []
            fig.update_layout(shapes=self._build_radius_shapes(existing_shapes))
            return alert, fig.to_dict(), False, False, False

        self.app.clientside_callback(
            """
            function(mode) {
                return mode !== 'none';
            }
            """,
            Output("tab-members-pmem-slider-collapse", "is_open"),
            Input("tab-members-filter-mode", "value"),
        )

        @self.app.callback(
            [
                Output("cluster-plot", "figure", allow_duplicate=True),
                Output("tab-cluster-members-output", "children", allow_duplicate=True),
            ],
            Input("tab-members-apply-filter", "n_clicks"),
            [
                State("cluster-plot", "figure"),
                State("tab-members-filter-mode", "value"),
                State("tab-members-pmem-slider", "value"),
            ],
            prevent_initial_call=True,
        )
        def apply_members_filter(n_clicks, current_figure, filter_mode, pmem_threshold):
            if not n_clicks or not self.selected_cluster:
                return dash.no_update, dash.no_update
            cluster_id = self.selected_cluster.get("merged_cluster_id")
            if cluster_id is None:
                return dash.no_update, dash.no_update
            trace_name = f"Members (ID {int(cluster_id)})"
            cache = (self.catred_handler.current_catred_data or {}) if self.catred_handler else {}
            entry = cache.get(trace_name)
            if not entry:
                return dash.no_update, dash.no_update
            ra = np.array(entry["ra"])
            dec = np.array(entry["dec"])
            pmem_zp = list(entry.get("pmem_zp", [float("nan")] * len(ra)))
            pmem_rs = list(entry.get("pmem_rs", [float("nan")] * len(ra)))
            if filter_mode in ("zp", "rs") and pmem_threshold is not None:
                pmem_vals = pmem_zp if filter_mode == "zp" else pmem_rs
                keep = np.array([
                    i for i, v in enumerate(pmem_vals)
                    if not (v != v) and v > pmem_threshold
                ], dtype=int)
                if len(keep) > 0:
                    ra = ra[keep]
                    dec = dec[keep]
                    pmem_zp = [pmem_zp[i] for i in keep]
                    pmem_rs = [pmem_rs[i] for i in keep]
                else:
                    ra = np.array([])
            fig = go.Figure(current_figure)
            fig.data = tuple(t for t in fig.data if not (getattr(t, "name", "") or "").startswith(trace_name))
            if len(ra) > 0:
                fig.add_trace(self._build_members_trace(ra, dec, cluster_id, pmem_zp=pmem_zp, pmem_rs=pmem_rs))
            n_total = len(entry["ra"])
            alert = _members_alert(n_total, len(ra), cluster_id)
            return fig.to_dict(), alert

