"""  
UI callbacks for cluster visualization
"""

import os
from pathlib import Path
import glob
from dash import Input, Output, State, html, dash, ALL, callback_context
import dash_bootstrap_components as dbc


class UICallbacks:
    """Handles UI-related callbacks"""

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
        self._setup_collapsible_callbacks()
        self._setup_file_configuration_callback()
        self._setup_file_browser_callbacks()

    def _setup_button_text_callbacks(self):
        """Setup callbacks to update button text based on current settings"""

        # Use a dummy interval to trigger initial callback and then button clicks
        @self.app.callback(
            Output("render-button", "children"),
            [Input("render-button", "n_clicks")],
            prevent_initial_call=False,
        )
        def update_main_button_text(n_clicks):
            """Update main render button text"""
            if n_clicks is None:
                n_clicks = 0
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
            Output("matching-clusters-switch", "disabled"),
            [Input("algorithm-dropdown", "value"), Input("merged-clusters-switch", "disabled")],
            prevent_initial_call=False,
        )
        def toggle_matching_clusters_switch(algorithm, merged_clusters):
            """Enable matching-clusters-switch only when algorithm is BOTH and merged_clusters is enabled"""
            # Enable the switch only when algorithm is 'BOTH' and merged_clusters is True
            is_disabled = (algorithm != "BOTH") and (not merged_clusters)
            print(
                f"🔄 Algorithm dropdown callback: algorithm={algorithm}, merged_clusters={merged_clusters}, matching-switch-disabled={is_disabled}"
            )
            return is_disabled

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

        # CatRed Sources Section
        @self.app.callback(
            [Output("catred-data-collapse", "is_open"), Output("catred-data-toggle", "children")],
            [Input("catred-data-toggle", "n_clicks")],
            prevent_initial_call=False,
        )
        def toggle_catred_data(n_clicks):
            """Toggle CatRed data section"""
            if n_clicks is None:
                return False, [html.I(className="fas fa-chevron-right me-2"), "🔬 CatRed Sources"]

            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [html.I(className=f"{icon} me-2"), "🔬 CatRed Sources"]

        # Mosaic / Healpix Mask Section
        @self.app.callback(
            [
                Output("image-controls-collapse", "is_open"),
                Output("image-controls-toggle", "children"),
            ],
            [Input("image-controls-toggle", "n_clicks")],
            prevent_initial_call=False,
        )
        def toggle_image_controls(n_clicks):
            """Toggle image controls section"""
            if n_clicks is None:
                return False, [
                    html.I(className="fas fa-chevron-right me-2"),
                    "🖼️ Mosaic / Healpix Mask",
                ]

            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [html.I(className=f"{icon} me-2"), "🖼️ Mosaic / Healpix Mask"]

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
        def toggle_file_browser(browse_clicks, close_clicks, cancel_clicks, select_clicks, 
                                is_open):
            """Toggle file browser modal and initialize directory"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update
            
            button_id = ctx.triggered[0]["prop_id"].split(".")[0]
            
            if button_id == "browse-file-button":
                # Get default directory from config
                default_dir = ""
                if self.config and hasattr(self.config, 'gluematchcat_dir'):
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
            if file_path and file_path.strip() and file_path.endswith('.xml'):
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
                return html.Div(
                    [
                        html.I(className="fas fa-exclamation-triangle text-warning me-2"),
                        "No file path provided"
                    ],
                    className="text-warning"
                ), dash.no_update
            
            # Validate file exists
            if not os.path.exists(file_path):
                return html.Div(
                    [
                        html.I(className="fas fa-exclamation-circle text-danger me-2"),
                        f"File not found: {os.path.basename(file_path)}"
                    ],
                    className="text-danger"
                ), dash.no_update
            
            # Validate it's an XML file
            if not file_path.endswith('.xml'):
                return html.Div(
                    [
                        html.I(className="fas fa-exclamation-circle text-danger me-2"),
                        "File must be an XML file"
                    ],
                    className="text-danger"
                ), dash.no_update
            
            # Update config if available
            if self.config:
                try:
                    # Update the config parser
                    if not self.config.config_parser.has_section('files'):
                        self.config.config_parser.add_section('files')
                    self.config.config_parser.set('files', 'gluematchcat_clusters', file_path)
                    
                    # Save to config file
                    if not Path(self.config._config_file_used).name.endswith('_temp.ini'):
                        newconfigfile_path = str(Path(self.config._config_file_used).with_stem(Path(self.config._config_file_used).stem + '_temp')) 
                    else:
                        newconfigfile_path = self.config._config_file_used
                    with open(newconfigfile_path, 'w') as f:
                        self.config.config_parser.write(f)
                    
                    # Clear ALL caches to force reload with new file
                    if self.data_loader:
                        # Clear in-memory cache
                        self.data_loader.data_cache.clear()
                        print(f"✓ Cleared in-memory data cache")
                        
                        # Clear disk cache entries for merged catalog
                        if hasattr(self.data_loader, 'cached') and self.data_loader.cached:
                            cache_keys_to_remove = []
                            for key in self.data_loader.cached.keys():
                                if 'merged_catalog' in key:
                                    cache_keys_to_remove.append(key)
                            for key in cache_keys_to_remove:
                                del self.data_loader.cached[key]
                                print(f"✓ Cleared disk cache entry: {key}")
                    
                    return html.Div(
                        [
                            html.I(className="fas fa-check-circle text-success me-2"),
                            f"Configuration updated! Click 'Render' to reload data with: {os.path.basename(file_path)}"
                        ],
                        className="text-success"
                    ), os.path.basename(file_path)
                    
                except Exception as e:
                    return html.Div(
                        [
                            html.I(className="fas fa-exclamation-circle text-danger me-2"),
                            f"Error updating config: {str(e)}"
                        ],
                        className="text-danger"
                    ), dash.no_update
            else:
                return html.Div(
                    [
                        html.I(className="fas fa-info-circle text-info me-2"),
                        "Config not available - changes will not persist"
                    ],
                    className="text-info"
                ), os.path.basename(file_path)
