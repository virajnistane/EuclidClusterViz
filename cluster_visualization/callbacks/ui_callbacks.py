"""
UI callbacks for cluster visualization
"""

import os
from pathlib import Path
import glob
from dash import Input, Output, State, html, dash, ALL, callback_context
import dash_bootstrap_components as dbc
import base64
import csv
import io

try:
    from cluster_visualization.callbacks.utils import get_idclusters_array
except ImportError:
    print("Warning: Could not import get_idclusters_array from utils. ID cluster upload functionality may be affected.")

class UICallbacks:
    """Handles UI-related callbacks"""

    DEFAULT_CLTILE_INFO_HELP_TEXT = "Color clusters by tile; show MER tile polygons"
    DEFAULT_UNMERGED_HELP_TEXT = "Clusters in individual tiles but absent from merged catalog"
    NO_INDIVIDUAL_CLTILE_DATA_MESSAGE = "No individual CL-tile data available"

    def __init__(self, app, config=None, data_loader=None):
        """
        Initialize UI callbacks.

        Args:
            app: Dash application instance
            config: Configuration object (optional)
            data_loader: DataLoader instance (optional)
        """
        self.app = app
        self.config = config
        self.data_loader = data_loader
        self.setup_callbacks()

    def setup_callbacks(self):
        """Setup all UI-related callbacks"""
        self._setup_button_text_callbacks()
        self._setup_button_state_callbacks()
        self._setup_catred_visibility_callback()
        self._setup_catred_render_color_callback()
        self._setup_catred_box_color_callback()
        self._setup_collapsible_callbacks()
        self._setup_config_display_callback()
        self._setup_file_configuration_callback()
        self._setup_file_browser_callbacks()
        self._setup_view_mode_callbacks()

    def _setup_button_text_callbacks(self):
        """Setup callbacks to update button text based on current settings"""

        # Use a dummy interval to trigger initial callback and then button clicks
        @self.app.callback(
            Output("render-button", "children"),
            [Input("render-button", "n_clicks"),
             Input("snr-render-button-pzwav", "n_clicks"),
             Input("snr-render-button-amico", "n_clicks"),
             Input("redshift-render-button", "n_clicks"),
             Input("idcluster-render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def update_main_button_text(n_clicks, snr_pzwav_clicks, snr_amico_clicks, redshift_clicks, idcluster_clicks):
            """Update main render button text"""
            if n_clicks is None:
                n_clicks = 0
            if any([snr_pzwav_clicks, snr_amico_clicks, redshift_clicks, idcluster_clicks]):
                n_clicks += 1
            return "🚀 Initial Render" if n_clicks == 0 else f"✅ Live Updates Active ({n_clicks})"

        @self.app.callback(
            Output("catred-render-button", "children"),
            [Input("catred-render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def update_catred_button_text(catred_n_clicks):
            """Update CATRED button text"""
            if catred_n_clicks is None:
                catred_n_clicks = 0
            return (
                f"🔍 Render CATRED Data ({catred_n_clicks})"
                if catred_n_clicks > 0
                else "🔍 Render CATRED Data"
            )

        @self.app.callback(
            Output("snr-render-button-pzwav", "children"),
            [Input("snr-render-button-pzwav", "n_clicks")],
            prevent_initial_call=False,
        )
        def update_snr_pzwav_button_text(snr_n_clicks):
            """Update PZWAV SNR button text"""
            if snr_n_clicks is None:
                snr_n_clicks = 0
            return [
                html.I(className="fas fa-filter me-2"),
                (
                    f"Apply SNR Filter (PZWAV) ({snr_n_clicks})"
                    if snr_n_clicks > 0
                    else "Apply SNR Filter (PZWAV)"
                ),
            ]

        @self.app.callback(
            Output("snr-render-button-amico", "children"),
            [Input("snr-render-button-amico", "n_clicks")],
            prevent_initial_call=False,
        )
        def update_snr_amico_button_text(snr_n_clicks):
            """Update AMICO SNR button text"""
            if snr_n_clicks is None:
                snr_n_clicks = 0
            return [
                html.I(className="fas fa-filter me-2"),
                (
                    f"Apply SNR Filter (AMICO) ({snr_n_clicks})"
                    if snr_n_clicks > 0
                    else "Apply SNR Filter (AMICO)"
                ),
            ]

        @self.app.callback(
            Output("redshift-render-button", "children"),
            [Input("redshift-render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def update_redshift_button_text(redshift_n_clicks):
            """Update redshift button text"""
            if redshift_n_clicks is None:
                redshift_n_clicks = 0
            return (
                f"🌌 Update Redshift Filter ({redshift_n_clicks})"
                if redshift_n_clicks > 0
                else "🌌 Update Redshift Filter"
            )

        @self.app.callback(
            Output("catred-clear-button", "children"),
            [Input("catred-clear-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def update_clear_button_text(clear_n_clicks):
            """Update clear button text with click count"""
            clear_n_clicks = clear_n_clicks or 0
            return (
                f"🗑️ Clear All CATRED ({clear_n_clicks})"
                if clear_n_clicks > 0
                else "🗑️ Clear All CATRED"
            )

    def _setup_button_state_callbacks(self):
        """Setup callbacks to enable/disable buttons based on conditions"""

        @self.app.callback(
            [
                Output("file-config-tab-control", "disabled"),
                Output("file-config-tab-control", "label"),
            ],
            [Input("render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def disable_file_config_tab(n_clicks):
            """Disable File Config tab if gluematchcat_clusters is not configured"""
            if self.config is None:
                return True, "📁 File Config (Not Available)"
            
            # Check if gluematchcat_clusters is configured
            gluematchcat_xml = self.config.get_gluematchcat_clusters_xml()
            if gluematchcat_xml is None:
                return True, "📁 File Config (GlueMatchCat XML Not Configured)"
            
            return False, "📁 File Config"

        @self.app.callback(
            [
                Output("snr-render-button-pzwav", "disabled"),
                Output("snr-render-button-amico", "disabled"),
                Output("redshift-render-button", "disabled"),
            ],
            [Input("render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def enable_snr_and_redshift_buttons(n_clicks):
            """Enable SNR and redshift filter buttons after initial render"""
            # Disable both buttons until initial render is clicked
            n_clicks = n_clicks or 0
            disabled = n_clicks == 0
            return disabled, disabled, disabled

        @self.app.callback(
            [
                Output("idcluster-render-button", "disabled"),
                Output("idcluster-status-display", "children"),
            ],
            [
                Input("idcluster-upload", "contents"),
                Input("idcluster-upload", "filename"),
            ],
            prevent_initial_call=False,
        )
        def enable_idcluster_button(upload_contents, upload_filename):
            """Enable Cluster-ID filter button and show uploaded entry count."""
            if not upload_contents or not upload_filename:
                return True, "No ID list uploaded"

            try:
                idcluster_array = get_idclusters_array(upload_contents, upload_filename)
                count = int(idcluster_array.size) if idcluster_array is not None else 0
                status = f"Uploaded {count} cluster IDs"

                return False, status

            except Exception as error:
                return True, f"Upload error: {error}"

        @self.app.callback(
            Output("matching-clusters-switch", "disabled"),
            [Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def toggle_matching_clusters_switch(algorithm):
            """Enable matching-clusters-switch only when algorithm is BOTH"""
            is_disabled = algorithm != "BOTH"
            print(
                f"🔄 Algorithm dropdown callback: algorithm={algorithm}, matching-switch-disabled={is_disabled}"
            )
            return is_disabled

        @self.app.callback(
            [
                Output("cltile-info-switch", "disabled"),
                Output("cltile-info-switch", "value"),
                Output("cltile-info-switch-help-text", "children"),
                Output("unmerged-clusters-switch", "disabled"),
                Output("unmerged-clusters-switch", "value"),
                Output("unmerged-clusters-switch-help-text", "children"),
            ],
            [Input("algorithm-dropdown", "value"), Input("render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def toggle_individual_cltile_switches(algorithm, _render_clicks):
            """Disable CL-tile-dependent switches when individual tile data is unavailable."""
            return self._get_individual_cltile_switch_state(algorithm)

        @self.app.callback(
            [
                Output("browse-file-button", "disabled"),
                Output("browse-file-button", "title"),
            ],
            [Input("browse-file-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def disable_browse_button_if_no_config(n_clicks):
            """Disable browse button if gluematchcat_clusters is not configured"""
            if self.config is None:
                return True, "Configuration not available"
            
            # Check if gluematchcat_clusters is configured
            gluematchcat_xml = self.config.get_gluematchcat_clusters_xml()
            if gluematchcat_xml is None:
                return True, "GlueMatchCat XML file not configured in config.ini"
            
            return False, "Browse for file"

    def _get_individual_cltile_switch_state(self, algorithm):
        """Compute disabled/value/help text state for CL-tile-dependent switches."""
        is_available = True
        unavailable_message = self.NO_INDIVIDUAL_CLTILE_DATA_MESSAGE

        if self.data_loader and hasattr(self.data_loader, "get_individual_cltile_data_availability"):
            is_available, unavailable_message = self.data_loader.get_individual_cltile_data_availability(
                algorithm
            )

        if is_available:
            return (
                False,
                dash.no_update,
                self.DEFAULT_CLTILE_INFO_HELP_TEXT,
                False,
                dash.no_update,
                self.DEFAULT_UNMERGED_HELP_TEXT,
            )

        return True, False, unavailable_message, True, False, unavailable_message

    def _setup_catred_visibility_callback(self):
        """Setup clientside callback to show/hide CATRED controls based on catred-mode-switch"""
        self.app.clientside_callback(
            """
            function(catredEnabled) {
                // Convert boolean to display style
                let displayStyle = catredEnabled ? 'block' : 'none';
                
                // Return the display style for all 3 container elements
                return [
                    {display: displayStyle},
                    {display: displayStyle}, 
                    {display: displayStyle}
                ];
            }
            """,
            [
                Output("catred-threshold-container", "style"),
                Output("magnitude-limit-container", "style"),
            ],
            #  Output('catred-controls-container', 'style')],
            [Input("catred-mode-switch", "value")],
            prevent_initial_call=False,
        )

    def _setup_catred_render_color_callback(self):
        """Clientside callback: update CATRED MER Tile trace marker color without re-render.

        Uses JS spread to shallow-clone only the affected trace objects, leaving large
        data arrays (x, y, customdata) as shared references — no extra allocation.
        Triggered by the color picker; figure is read as State so figure changes alone
        do not re-trigger this callback.
        """
        self.app.clientside_callback(
            """
            function(markerColor, figure) {
                if (!figure || !figure.data || !markerColor) {
                    return window.dash_clientside.no_update;
                }
                var changed = false;
                var newData = figure.data.map(function(trace) {
                    if (trace.name &&
                            trace.name.indexOf('CATRED') !== -1 &&
                            trace.name.indexOf('MER Tile') !== -1) {
                        changed = true;
                        return Object.assign({}, trace, {
                            marker: Object.assign({}, trace.marker, {
                                line: Object.assign({}, trace.marker && trace.marker.line,
                                                    {color: markerColor})
                            })
                        });
                    }
                    return trace;
                });
                if (!changed) return window.dash_clientside.no_update;
                return Object.assign({}, figure, {data: newData});
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input("catred-render-marker-color", "value"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

    def _setup_catred_box_color_callback(self):
        """Clientside callback: update CATRED Boxed trace marker color without re-render.

        Mirrors _setup_catred_render_color_callback but targets traces named
        'CATRED * - Boxed' (cluster-click box panel) instead of 'CATRED * MER Tile'.
        """
        self.app.clientside_callback(
            """
            function(markerColor, figure) {
                if (!figure || !figure.data || !markerColor) {
                    return window.dash_clientside.no_update;
                }
                var changed = false;
                var newData = figure.data.map(function(trace) {
                    if (trace.name &&
                            trace.name.indexOf('CATRED') !== -1 &&
                            trace.name.indexOf('Boxed') !== -1) {
                        changed = true;
                        return Object.assign({}, trace, {
                            marker: Object.assign({}, trace.marker, {
                                line: Object.assign({}, trace.marker && trace.marker.line,
                                                    {color: markerColor})
                            })
                        });
                    }
                    return trace;
                });
                if (!changed) return window.dash_clientside.no_update;
                return Object.assign({}, figure, {data: newData});
            }
            """,
            Output("cluster-plot", "figure", allow_duplicate=True),
            Input("tab-catred-marker-color-picker", "value"),
            State("cluster-plot", "figure"),
            prevent_initial_call=True,
        )

    def _setup_collapsible_callbacks(self):
        """Setup callbacks for collapsible sections"""

        # Detected Clusters Section
        @self.app.callback(
            [
                Output("clusters-settings-collapse", "is_open"),
                Output("clusters-settings-toggle", "children"),
            ],
            [Input("clusters-settings-toggle", "n_clicks")],
            prevent_initial_call=False,
        )
        def toggle_clusters_settings(n_clicks):
            """Toggle clusters settings section"""
            if n_clicks is None:
                return False, [  # 🔧 Changed from True to False
                    html.I(className="fas fa-chevron-right me-2"),  # 🔧 Changed to right arrow
                    "🎯 Detected Clusters",
                ]

            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [html.I(className=f"{icon} me-2"), "🎯 Detected Clusters"]

        # Display Options Section
        @self.app.callback(
            [
                Output("display-options-collapse", "is_open"),
                Output("display-options-toggle", "children"),
            ],
            [Input("display-options-toggle", "n_clicks")],
            prevent_initial_call=False,
        )
        def toggle_display_options(n_clicks):
            """Toggle display options section"""
            if n_clicks is None:
                return False, [  # 🔧 Changed from True to False to match layout
                    html.I(className="fas fa-chevron-right me-2"),  # 🔧 Changed to right arrow
                    "🎨 Display Options",
                ]

            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [html.I(className=f"{icon} me-2"), "🎨 Display Options"]

        # Mask Section
        @self.app.callback(
            [
                Output("mask-controls-collapse", "is_open"),
                Output("mask-controls-toggle", "children"),
            ],
            [Input("mask-controls-toggle", "n_clicks")],
            prevent_initial_call=False,
        )
        def toggle_mask_controls(n_clicks):
            if n_clicks is None:
                return False, [html.I(className="fas fa-chevron-right me-2"), "🎭 Mask"]
            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [html.I(className=f"{icon} me-2"), "🎭 Mask"]

        # Mosaic Section
        @self.app.callback(
            [
                Output("image-controls-collapse", "is_open", allow_duplicate=True),
                Output("image-controls-toggle", "children"),
            ],
            [Input("image-controls-toggle", "n_clicks")],
            prevent_initial_call="initial_duplicate",
        )
        def toggle_image_controls(n_clicks):
            """Toggle image controls section"""
            if n_clicks is None:
                return False, [
                    html.I(className="fas fa-chevron-right me-2"),
                    "🖼️ Mosaic",
                ]

            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [html.I(className=f"{icon} me-2"), "🖼️ Mosaic"]

    def _setup_config_display_callback(self):
        """Setup callback to display configuration parameters"""

        @self.app.callback(
            [
                Output("config-merged-catalog", "children"),
                Output("config-detintile-list", "children"),
            ],
            [Input("render-button", "n_clicks"), Input("algorithm-dropdown", "value")],
            prevent_initial_call=False,
        )
        def display_config_info(n_clicks, algorithm):
            """Display current configuration parameters"""
            if self.config is None:
                return (
                    html.Div(
                        [
                            dbc.Badge("Not Available", color="warning", className="me-2"),
                            html.Span("Configuration not loaded", className="text-muted"),
                        ]
                    ),
                    html.Div(
                        [
                            dbc.Badge("Not Available", color="warning", className="me-2"),
                            html.Span("Configuration not loaded", className="text-muted"),
                        ]
                    ),
                )

            try:
                # Get merged catalog file
                gluematchcat_path = self.config.get_gluematchcat_clusters_xml()
                
                merged_catalog_display = None
                if gluematchcat_path and os.path.exists(gluematchcat_path):
                    # Show abbreviated path (last 2 segments + filename)
                    path_parts = Path(gluematchcat_path).parts
                    if len(path_parts) > 2:
                        short_path = str(Path(*path_parts[-2:]))
                    else:
                        short_path = os.path.basename(gluematchcat_path)
                    
                    merged_catalog_display = html.Div(
                        [
                            dbc.Badge("GlueMatchCat", color="success", className="me-2"),
                            html.Span(
                                short_path,
                                className="text-primary font-monospace small",
                                title=gluematchcat_path,
                                style={"cursor": "help"},
                            ),
                        ]
                    )
                else:
                    # Try algorithm-specific merged catalog
                    try:
                        mergedet_files = self.config.get_mergedetcat_xml_files(algorithm)
                        if mergedet_files:
                            # Get the first available file
                            first_key = next(iter(mergedet_files))
                            mergedet_path = mergedet_files[first_key]
                            
                            if mergedet_path and os.path.exists(mergedet_path):
                                path_parts = Path(mergedet_path).parts
                                if len(path_parts) > 2:
                                    short_path = str(Path(*path_parts[-2:]))
                                else:
                                    short_path = os.path.basename(mergedet_path)
                                
                                merged_catalog_display = html.Div(
                                    [
                                        dbc.Badge(f"MergeDetCat ({algorithm})", color="info", className="me-2"),
                                        html.Span(
                                            short_path,
                                            className="text-primary font-monospace small",
                                            title=mergedet_path,
                                            style={"cursor": "help"},
                                        ),
                                    ]
                                )
                            else:
                                merged_catalog_display = html.Div(
                                    [
                                        dbc.Badge("Not Found", color="danger", className="me-2"),
                                        html.Span("File configured but missing", className="text-muted small"),
                                    ]
                                )
                        else:
                            merged_catalog_display = html.Div(
                                [
                                    dbc.Badge("Not Configured", color="warning", className="me-2"),
                                    html.Span("No merged catalog configured", className="text-muted small"),
                                ]
                            )
                    except Exception as e:
                        merged_catalog_display = html.Div(
                            [
                                dbc.Badge("Error", color="danger", className="me-2"),
                                html.Span(f"Error: {str(e)}", className="text-danger small"),
                            ]
                        )

                # Get DetInTile list files
                detintile_display = None
                try:
                    detintile_files = self.config.get_detintile_list_files(algorithm)
                    if detintile_files:
                        detintile_items = []
                        for key, json_path in detintile_files.items():
                            if json_path and os.path.exists(json_path):
                                path_parts = Path(json_path).parts
                                if len(path_parts) > 2:
                                    short_path = str(Path(*path_parts[-2:]))
                                else:
                                    short_path = os.path.basename(json_path)
                                
                                # Extract algorithm name from key
                                algo_name = key.replace("detintile_", "").replace("_list", "").upper()
                                
                                detintile_items.append(
                                    html.Div(
                                        [
                                            dbc.Badge(algo_name, color="primary", className="me-2"),
                                            html.Span(
                                                short_path,
                                                className="text-info font-monospace small",
                                                title=json_path,
                                                style={"cursor": "help"},
                                            ),
                                        ],
                                        className="mb-1",
                                    )
                                )
                            else:
                                algo_name = key.replace("detintile_", "").replace("_list", "").upper()
                                detintile_items.append(
                                    html.Div(
                                        [
                                            dbc.Badge(algo_name, color="danger", className="me-2"),
                                            html.Span("File missing", className="text-muted small"),
                                        ],
                                        className="mb-1",
                                    )
                                )
                        
                        detintile_display = html.Div(detintile_items)
                    else:
                        detintile_display = html.Div(
                            [
                                dbc.Badge("Not Configured", color="warning", className="me-2"),
                                html.Span("No tile list configured", className="text-muted small"),
                            ]
                        )
                except Exception as e:
                    detintile_display = html.Div(
                        [
                            dbc.Badge("Error", color="danger", className="me-2"),
                            html.Span(f"Error: {str(e)}", className="text-danger small"),
                        ]
                    )

                return merged_catalog_display, detintile_display

            except Exception as e:
                error_display = html.Div(
                    [
                        dbc.Badge("Error", color="danger", className="me-2"),
                        html.Span(str(e), className="text-danger small"),
                    ]
                )
                return error_display, error_display

    def _setup_file_configuration_callback(self):
        """Setup callback to display current gluematchcat file"""

        @self.app.callback(
            Output("gluematchcat-file-display", "value"),
            [Input("render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def display_current_file(n_clicks):
            """Display current gluematchcat XML file basename"""
            if self.config is None:
                return "Config not available"

            try:
                gluematchcat_path = self.config.get_gluematchcat_clusters_xml()
                if gluematchcat_path and os.path.exists(gluematchcat_path):
                    return os.path.basename(gluematchcat_path)
                else:
                    return "No file configured"
            except Exception as e:
                return f"Error: {str(e)}"

    def _setup_file_browser_callbacks(self):
        """Setup callbacks for file browser modal"""

        # Open file browser modal when browse button is clicked
        @self.app.callback(
            [
                Output("file-browser-modal", "is_open"),
                Output("file-browser-directory", "value"),
            ],
            [
                Input("browse-file-button", "n_clicks"),
                Input("file-browser-close", "n_clicks"),
                Input("file-browser-cancel", "n_clicks"),
                Input("file-browser-select", "n_clicks"),
            ],
            [State("file-browser-modal", "is_open")],
            prevent_initial_call=True,
        )
        def toggle_file_browser(browse_clicks, close_clicks, cancel_clicks, select_clicks, is_open):
            """Toggle file browser modal and initialize directory"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update

            button_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if button_id == "browse-file-button":
                # Check if gluematchcat_clusters is configured
                if self.config is None or self.config.get_gluematchcat_clusters_xml() is None:
                    # Don't open modal if not configured
                    return False, dash.no_update
                
                # Get default directory from config
                default_dir = ""
                if self.config and hasattr(self.config, "gluematchcat_dir"):
                    default_dir = self.config.gluematchcat_dir or ""
                return True, default_dir
            else:
                # Close modal
                return False, dash.no_update

        # List files when directory changes or refresh is clicked
        @self.app.callback(
            Output("file-browser-list", "children"),
            [
                Input("file-browser-directory", "value"),
                Input("file-browser-refresh", "n_clicks"),
            ],
            prevent_initial_call=False,
        )
        def list_files(directory, refresh_clicks):
            """List XML files in the specified directory"""
            if not directory or not os.path.exists(directory):
                return html.Div(
                    [
                        html.I(className="fas fa-exclamation-triangle text-warning me-2"),
                        "Invalid or empty directory path",
                    ],
                    className="text-muted text-center p-3",
                )

            try:
                # Find all XML files in directory
                xml_files = []
                leveldeep = 0
                while leveldeep <= 2:  # Search up to 2 levels deep
                    pattern = os.path.join(directory, *["*"] * leveldeep, "unified_clusters*.xml")
                    xml_files.extend(glob.glob(pattern))
                    leveldeep += 1

                if not xml_files:
                    return html.Div(
                        [
                            html.I(className="fas fa-folder-open text-muted me-2"),
                            "No XML files found in this directory",
                        ],
                        className="text-muted text-center p-3",
                    )

                # Create clickable list of files
                file_list = []
                for xml_file in sorted(xml_files):
                    filename = os.path.relpath(xml_file, directory)
                    file_list.append(
                        dbc.Button(
                            [
                                html.I(className="fas fa-file-code me-2"),
                                filename,
                            ],
                            id={"type": "file-item", "index": xml_file},
                            color="light",
                            className="w-100 text-start mb-2",
                            size="sm",
                            n_clicks=0,
                        )
                    )

                return html.Div(file_list)

            except Exception as e:
                return html.Div(
                    [
                        html.I(className="fas fa-exclamation-circle text-danger me-2"),
                        f"Error reading directory: {str(e)}",
                    ],
                    className="text-danger p-3",
                )

        # Store selected file and enable select button
        @self.app.callback(
            [
                Output("selected-file-path", "data"),
                Output("file-browser-select", "disabled"),
            ],
            [Input({"type": "file-item", "index": ALL}, "n_clicks")],
            [State({"type": "file-item", "index": ALL}, "id")],
            prevent_initial_call=True,
        )
        def select_file(n_clicks_list, button_ids):
            """Store selected file path when a file is clicked"""
            ctx = callback_context
            if not ctx.triggered or not any(n_clicks_list):
                return dash.no_update, dash.no_update

            # Find which button was clicked
            triggered_id = ctx.triggered_id
            if triggered_id and isinstance(triggered_id, dict):
                selected_path = triggered_id.get("index")
                if selected_path:
                    return selected_path, False

            return dash.no_update, dash.no_update

        # Apply selected file to input when Select button is clicked
        @self.app.callback(
            Output("gluematchcat-file-input", "value"),
            [Input("file-browser-select", "n_clicks")],
            [State("selected-file-path", "data")],
            prevent_initial_call=True,
        )
        def apply_selected_file(select_clicks, selected_path):
            """Apply selected file path to the input field"""
            if selected_path:
                return selected_path
            return dash.no_update

        # Enable apply button when file input changes
        @self.app.callback(
            Output("apply-file-config-button", "disabled"),
            [Input("gluematchcat-file-input", "value")],
            prevent_initial_call=False,
        )
        def enable_apply_button(file_path):
            """Enable apply button when a valid file path is entered"""
            if file_path and file_path.strip() and file_path.endswith(".xml"):
                return False
            return True

        # Handle apply button click
        @self.app.callback(
            [
                Output("file-config-status", "children"),
                Output("gluematchcat-file-display", "value", allow_duplicate=True),
            ],
            [Input("apply-file-config-button", "n_clicks")],
            [State("gluematchcat-file-input", "value")],
            prevent_initial_call=True,
        )
        def apply_file_config(n_clicks, file_path):
            """Apply the new file configuration"""
            if not file_path or not file_path.strip():
                return (
                    html.Div(
                        [
                            html.I(className="fas fa-exclamation-triangle text-warning me-2"),
                            "No file path provided",
                        ],
                        className="text-warning",
                    ),
                    dash.no_update,
                )

            # Validate file exists
            if not os.path.exists(file_path):
                return (
                    html.Div(
                        [
                            html.I(className="fas fa-exclamation-circle text-danger me-2"),
                            f"File not found: {os.path.basename(file_path)}",
                        ],
                        className="text-danger",
                    ),
                    dash.no_update,
                )

            # Validate it's an XML file
            if not file_path.endswith(".xml"):
                return (
                    html.Div(
                        [
                            html.I(className="fas fa-exclamation-circle text-danger me-2"),
                            "File must be an XML file",
                        ],
                        className="text-danger",
                    ),
                    dash.no_update,
                )

            # Update config if available
            if self.config:
                try:
                    # Update the config parser
                    if not self.config.config_parser.has_section("files"):
                        self.config.config_parser.add_section("files")
                    self.config.config_parser.set("files", "gluematchcat_clusters", file_path)

                    # Save to config file in tmp directory
                    config_path = Path(self.config._config_file_used)
                    
                    # Determine the base config file (remove _temp if present)
                    if config_path.name.endswith("_temp.ini"):
                        base_stem = config_path.stem.replace("_temp", "")
                        # Get parent of current file, and if it's 'tmp', go one level up
                        if config_path.parent.name == "tmp":
                            config_parent = config_path.parent.parent
                        else:
                            config_parent = config_path.parent
                    else:
                        base_stem = config_path.stem
                        config_parent = config_path.parent
                    
                    # Always place temp config in tmp directory
                    tmp_dir = config_parent / "tmp"
                    tmp_dir.mkdir(exist_ok=True)
                    newconfigfile_path = str(tmp_dir / f"{base_stem}_temp.ini")
                    with open(newconfigfile_path, "w") as f:
                        self.config.config_parser.write(f)

                    # Clear ALL caches to force reload with new file
                    if self.data_loader:
                        # Clear in-memory cache
                        self.data_loader.data_cache.clear()
                        print(f"✓ Cleared in-memory data cache")

                        # Clear disk cache entries for merged catalog
                        if hasattr(self.data_loader, "cached") and self.data_loader.cached:
                            cache_keys_to_remove = []
                            for key in self.data_loader.cached.keys():
                                if "merged_catalog" in key:
                                    cache_keys_to_remove.append(key)
                            for key in cache_keys_to_remove:
                                del self.data_loader.cached[key]
                                print(f"✓ Cleared disk cache entry: {key}")

                    return html.Div(
                        [
                            html.I(className="fas fa-check-circle text-success me-2"),
                            f"Configuration updated! Click 'Render' to reload data with: {os.path.basename(file_path)}",
                        ],
                        className="text-success",
                    ), os.path.basename(file_path)

                except Exception as e:
                    return (
                        html.Div(
                            [
                                html.I(className="fas fa-exclamation-circle text-danger me-2"),
                                f"Error updating config: {str(e)}",
                            ],
                            className="text-danger",
                        ),
                        dash.no_update,
                    )
            else:
                return html.Div(
                    [
                        html.I(className="fas fa-info-circle text-info me-2"),
                        "Config not available - changes will not persist",
                    ],
                    className="text-info",
                ), os.path.basename(file_path)

    # Helper functions

    # def _count_uploaded_id_entries(self, upload_contents, filename):
    #     """Count uploaded entries for txt/dat files or CSV values."""
    #     if not upload_contents or not filename:
    #         return 0

    #     _, content_string = upload_contents.split(",", 1)
    #     decoded_text = base64.b64decode(content_string).decode("utf-8", errors="ignore")
    #     suffix = Path(filename).suffix.lower()

    #     if suffix in {".txt", ".dat"}:
    #         return sum(1 for line in decoded_text.splitlines() if line.strip())

    #     if suffix == ".csv":
    #         reader = csv.reader(io.StringIO(decoded_text))
    #         return sum(1 for row in reader for value in row if str(value).strip())

    def _setup_view_mode_callbacks(self):
        """Clientside callbacks for switching between Standard (Plotly) and Aladin views."""

        # Toggle button clicks → update view-mode-store
        self.app.clientside_callback(
            """
            function(plotlyClicks, aladinClicks, currentMode) {
                const triggered = window.dash_clientside.callback_context.triggered;
                if (!triggered || triggered.length === 0) {
                    return window.dash_clientside.no_update;
                }
                const prop = triggered[0].prop_id;
                if (prop.includes('view-mode-plotly-btn')) return 'plotly';
                if (prop.includes('view-mode-aladin-btn')) return 'aladin';
                return window.dash_clientside.no_update;
            }
            """,
            Output("view-mode-store", "data"),
            [Input("view-mode-plotly-btn", "n_clicks"),
             Input("view-mode-aladin-btn", "n_clicks")],
            State("view-mode-store", "data"),
            prevent_initial_call=True,
        )

        # image-source-radio (in Mosaic sidebar) → view-mode-store
        self.app.clientside_callback(
            """
            function(radioVal) {
                if (radioVal === 'aladin') return 'aladin';
                if (radioVal === 'mosaic') return 'plotly';
                return window.dash_clientside.no_update;
            }
            """,
            Output("view-mode-store", "data", allow_duplicate=True),
            Input("image-source-radio", "value"),
            prevent_initial_call=True,
        )

        # view-mode-store → show/hide containers, button styles, mosaic controls, interval
        self.app.clientside_callback(
            """
            function(mode) {
                const isPlotly = mode === 'plotly';
                const isAladin = mode === 'aladin';
                const plotlyStyle = {display: isPlotly ? 'block' : 'none'};
                const aladinStyle = {display: isAladin ? 'block' : 'none'};
                const plotlyOutline = !isPlotly;
                const aladinOutline = !isAladin;
                const aladinIntervalDisabled = !isAladin;
                const merControlsStyle = {display: isAladin ? 'none' : 'block'};
                const surveyDropdownStyle = {display: isAladin ? 'block' : 'none'};
                const radioVal = isAladin ? 'aladin' : 'mosaic';
                // Show skeleton immediately when switching to Aladin; JS bridge hides it on init
                const skeletonStyle = isAladin
                    ? {display: 'flex', position: 'absolute', inset: '0', zIndex: '10', borderRadius: '8px'}
                    : {display: 'none'};
                return [plotlyStyle, aladinStyle, plotlyOutline, aladinOutline,
                        aladinIntervalDisabled, merControlsStyle, surveyDropdownStyle, radioVal,
                        skeletonStyle];
            }
            """,
            [Output("plotly-view-container", "style"),
             Output("aladin-view-container", "style"),
             Output("view-mode-plotly-btn", "outline"),
             Output("view-mode-aladin-btn", "outline"),
             Output("aladin-click-poll-interval", "disabled"),
             Output("mer-mosaic-controls", "style"),
             Output("aladin-survey-dropdown", "style"),
             Output("image-source-radio", "value"),
             Output("aladin-skeleton", "style")],
            Input("view-mode-store", "data"),
        )

        # Count cluster points in viewport → enable/disable Aladin button + store count
        # Uses relayoutData (fires on zoom/pan) + figure State (has trace data + stable ranges)
        self.app.clientside_callback(
            """
            function(relayoutData, figure) {
                var NO_UPDATE = window.dash_clientside.no_update;
                if (!figure || !figure.layout) return [true, NO_UPDATE];

                // Resolve viewport: prefer relayoutData values, fall back to figure layout
                var raMin, raMax, decMin, decMax;
                if (relayoutData) {
                    if ('xaxis.range[0]' in relayoutData) {
                        raMin = relayoutData['xaxis.range[0]']; raMax = relayoutData['xaxis.range[1]'];
                        decMin = relayoutData['yaxis.range[0]']; decMax = relayoutData['yaxis.range[1]'];
                    } else if (relayoutData['xaxis.range']) {
                        raMin = relayoutData['xaxis.range'][0]; raMax = relayoutData['xaxis.range'][1];
                        decMin = relayoutData['yaxis.range'][0]; decMax = relayoutData['yaxis.range'][1];
                    }
                }
                if (raMin == null) {
                    var layout = figure.layout;
                    var xr = (layout.xaxis || {}).range;
                    var yr = (layout.yaxis || {}).range;
                    if (!xr || !yr) return [true, NO_UPDATE];
                    raMin = xr[0]; raMax = xr[1]; decMin = yr[0]; decMax = yr[1];
                }
                var tmp;
                if (raMin > raMax) { tmp = raMin; raMin = raMax; raMax = tmp; }
                if (decMin > decMax) { tmp = decMin; decMin = decMax; decMax = tmp; }

                var count = 0;
                (figure.data || []).forEach(function(trace) {
                    var name = (trace.name || '');
                    if (name.indexOf('Merged') < 0 && name.indexOf('PZWAV') < 0 && name.indexOf('AMICO') < 0) return;
                    if (name.indexOf('CATRED') === 0) return;            // pure CATRED scatter traces
                    if (name.indexOf('in CATRED region') >= 0) return;  // glow halos BOTH-algo: "Merged PZWAV (in CATRED region)"
                    // single-algo glow: "PZWAV (Merged, near CATRED)" — no cluster-count suffix
                    // single-algo data: "PZWAV (Merged, near CATRED) - N clusters" — has suffix, must be counted
                    if (name.indexOf('near CATRED') >= 0 && name.indexOf(' clusters') < 0) return;
                    var xs = trace.x || [];
                    var ys = trace.y || [];
                    for (var i = 0; i < xs.length; i++) {
                        if (xs[i] >= raMin && xs[i] <= raMax && ys[i] >= decMin && ys[i] <= decMax) {
                            count++;
                        }
                    }
                });
                var disabled = count !== 1;
                var storeVal = {count: count, ra: [raMin, raMax], dec: [decMin, decMax], ts: Date.now()};
                var radioOptions = [
                    {label: ' MER Mosaic', value: 'mosaic'},
                    {label: ' Aladin Sky', value: 'aladin', disabled: disabled}
                ];
                return [disabled, storeVal, radioOptions];
            }
            """,
            [Output("view-mode-aladin-btn", "disabled"),
             Output("viewport-cluster-count-store", "data"),
             Output("image-source-radio", "options")],
            [Input("cluster-plot", "relayoutData"),
             Input("cluster-plot", "figure")],
            prevent_initial_call=False,
        )

        # Aladin Lite JS bridge: lazy-load CDN, init viewer, push catalog overlays.
        # Mask is added as a HiPS overlay image layer (no server data needed).
        self.app.clientside_callback(
            """
            function(overlayData) {
                if (!overlayData) return window.dash_clientside.no_update;

                function doAladinInit(data) {
                    var vp  = data.viewport || {};
                    var ra  = vp.ra  != null ? vp.ra  : 180.0;
                    var dec = vp.dec != null ? vp.dec : 0.0;
                    var fov = vp.fov != null ? vp.fov : 1.0;
                    var survey = data.survey || 'P/DSS2/color';

                    function setupCatalogs(aladin) {
                        // Remove old catalog layers (keep image layers)
                        try { aladin.removeLayers(); } catch(e) {}

                        // Hide skeleton as soon as Aladin is positioned — catalogs added async below
                        var sk = document.getElementById('aladin-skeleton');
                        if (sk) sk.style.display = 'none';

                        // Build source arrays (cheap — just JS objects, no render yet)
                        var pzwavCat = A.catalog({name: 'PZWAV Clusters', color: '#ff6600', shape: 'x', sourceSize: 14});
                        var amicoCat = A.catalog({name: 'AMICO Clusters', color: '#ff6600', shape: 'cross', sourceSize: 14});
                        var pzwavSrcs = [], amicoSrcs = [];
                        (data.clusters || []).forEach(function(r) {
                            var name = (r.name || '').toUpperCase();
                            var src = A.source(r.ra, r.dec, {name: r.name || ''});
                            if (name.indexOf('AMICO') >= 0) { amicoSrcs.push(src); }
                            else { pzwavSrcs.push(src); }
                        });
                        var catredCat = A.catalog({name: 'CATRED', color: '#00ffff', shape: 'circle', sourceSize: 8});
                        var catredSrcs = (data.catred || []).map(function(r) {
                            return A.source(r.ra, r.dec, {name: r.name || 'CATRED'});
                        });

                        // Add catalogs on next animation frame so Aladin sky tiles can start loading first
                        requestAnimationFrame(function() {
                            if (pzwavSrcs.length) pzwavCat.addSources(pzwavSrcs);
                            if (amicoSrcs.length) amicoCat.addSources(amicoSrcs);
                            aladin.addCatalog(pzwavCat);
                            aladin.addCatalog(amicoCat);
                            requestAnimationFrame(function() {
                                if (catredSrcs.length) catredCat.addSources(catredSrcs);
                                aladin.addCatalog(catredCat);
                            });
                        });
                    }

                    var doInit = function() {
                        if (window._aladinInstance) {
                            window._aladinInstance.gotoRaDec(ra, dec);
                            window._aladinInstance.setFov(fov);
                            window._aladinInstance.setImageSurvey(survey);
                            setupCatalogs(window._aladinInstance);
                        } else {
                            // Wait for #aladin-div to be visible and sized before init
                            // (Aladin v3 reads canvas size at creation; div hidden = blank)
                            var attempts = 0;
                            function tryInit() {
                                var divEl = document.getElementById('aladin-div');
                                if (!divEl || divEl.offsetWidth === 0 || divEl.offsetHeight === 0) {
                                    if (attempts++ < 40) { setTimeout(tryInit, 50); }
                                    return;
                                }
                                var inst = A.aladin('#aladin-div', {
                                    target: ra + ' ' + dec,
                                    fov: fov,
                                    survey: survey,
                                    cooFrame: 'J2000',
                                    showReticle: false,
                                    showZoomControl: false,
                                    showLayersControl: true,
                                    showFrame: false,
                                    showGotoControl: false,
                                    showShareControl: false,
                                    showProjectionControl: false
                                });
                                window._aladinInstance = inst;

                                // HEALPix detection mask as HiPS overlay layer
                                try {
                                    var maskHips = inst.createImageSurvey(
                                        'mask_detcl', 'Detection Mask',
                                        'https://erass-cluster-inspector.com/euclid/hips/mask_detcl/',
                                        'equatorial', 5, {imgFormat: 'png'}
                                    );
                                    window._aladinMaskLayer = inst.setOverlayImageLayer(maskHips, 'mask_detcl');
                                    window._aladinMaskLayer.setOpacity(0.3);
                                } catch(e) { console.warn('[Aladin] mask HiPS failed:', e); }

                                // Click bridge
                                try {
                                    inst.on('objectsSelected', function(objs) {
                                        if (objs && objs.length > 0) {
                                            var o = objs[0];
                                            window._aladinPendingClick = {
                                                ra: o.ra, dec: o.dec,
                                                name: (o.data && o.data.name) ? o.data.name : '',
                                                timestamp: Date.now()
                                            };
                                        }
                                    });
                                } catch(e) {}

                                setupCatalogs(inst);
                            }
                            tryInit();
                        }
                    };

                    if (typeof A !== 'undefined' && A.init && typeof A.init.then === 'function') {
                        A.init.then(doInit).catch(function(e) { console.error('[Aladin] A.init failed:', e); });
                    } else if (typeof A !== 'undefined') {
                        doInit();
                    }
                }

                // Lazy-load Aladin Lite CSS + JS from CDN on first call
                if (!document.getElementById('aladin-css')) {
                    var link = document.createElement('link');
                    link.id = 'aladin-css'; link.rel = 'stylesheet';
                    link.href = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.min.css';
                    document.head.appendChild(link);
                }
                if (!document.getElementById('aladin-js')) {
                    var script = document.createElement('script');
                    script.id = 'aladin-js'; script.charset = 'utf-8';
                    script.src = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js';
                    script.onload = function() { doAladinInit(overlayData); };
                    document.head.appendChild(script);
                    return window.dash_clientside.no_update;
                }

                doAladinInit(overlayData);
                return window.dash_clientside.no_update;
            }
            """,
            Output("aladin-init-dummy", "children"),
            Input("aladin-overlay-data-store", "data"),
            prevent_initial_call=True,
        )

        # When Aladin survey dropdown changes, update the live instance survey
        self.app.clientside_callback(
            """
            function(survey) {
                if (survey && window._aladinInstance) {
                    window._aladinInstance.setImageSurvey(survey);
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("aladin-init-dummy", "children", allow_duplicate=True),
            Input("aladin-survey-dropdown", "value"),
            prevent_initial_call=True,
        )

        # Aladin click poll: dcc.Interval → aladin-click-store
        self.app.clientside_callback(
            """
            function(n) {
                if (window._aladinPendingClick) {
                    var data = window._aladinPendingClick;
                    window._aladinPendingClick = null;
                    return data;
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("aladin-click-store", "data"),
            Input("aladin-click-poll-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Pre-fetch Aladin CDN assets ~3s after page load, then pre-init hidden instance
        self.app.clientside_callback(
            """
            function(n) {
                function maybePreInit() {
                    if (window._aladinInstance) return;
                    var divEl = document.getElementById('aladin-div');
                    if (!divEl || divEl.offsetWidth === 0 || divEl.offsetHeight === 0) return;
                    try {
                        var doPreInit = function() {
                            if (window._aladinInstance) return;
                            var inst = A.aladin('#aladin-div', {
                                target: '180 0', fov: 1.0,
                                survey: 'P/DSS2/color',
                                cooFrame: 'J2000',
                                showReticle: false, showZoomControl: false,
                                showLayersControl: true, showFrame: false,
                                showGotoControl: false, showShareControl: false,
                                showProjectionControl: false
                            });
                            window._aladinInstance = inst;
                        };
                        if (typeof A !== 'undefined' && A.init && typeof A.init.then === 'function') {
                            A.init.then(doPreInit).catch(function() {});
                        } else if (typeof A !== 'undefined') {
                            doPreInit();
                        }
                    } catch(e) {}
                }
                if (!document.getElementById('aladin-css')) {
                    var link = document.createElement('link');
                    link.id = 'aladin-css'; link.rel = 'stylesheet';
                    link.href = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.min.css';
                    document.head.appendChild(link);
                }
                if (!document.getElementById('aladin-js')) {
                    var script = document.createElement('script');
                    script.id = 'aladin-js'; script.charset = 'utf-8';
                    script.src = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js';
                    script.onload = function() { setTimeout(maybePreInit, 200); };
                    document.head.appendChild(script);
                } else {
                    maybePreInit();
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("aladin-init-dummy", "children", allow_duplicate=True),
            Input("aladin-preload-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Disable mosaic cutout button when in ESA Sky or Aladin mode
        self.app.clientside_callback(
            """
            function(mode) {
                const disabled = mode === 'aladin';
                return [disabled, disabled];
            }
            """,
            [Output("tab-cutout-button", "disabled"),
             Output("tab-generate-cutout", "disabled")],
            Input("view-mode-store", "data"),
        )

    #     return 0