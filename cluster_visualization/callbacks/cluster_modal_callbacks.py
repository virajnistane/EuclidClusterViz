"""
Cluster modal callbacks for cluster visualization.

Handles cluster selection, modal dialog interactions, and cluster-specific actions
like cutout generation, PHZ analysis, and data export.
"""

import dash
from dash import Input, Output, State, html, callback_context
import plotly.graph_objs as go
import pandas as pd
import dash_bootstrap_components as dbc
import json


class ClusterModalCallbacks:
    """Handles cluster modal and action callbacks"""
    
    def __init__(self, app, data_loader, catred_handler, trace_creator, figure_manager):
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
        self._setup_parameter_sync_callbacks()
    
    def _setup_cluster_click_callback(self):
        """Setup callback to detect cluster clicks and show in cluster tab"""
        @self.app.callback(
            [Output('cluster-no-selection', 'style'),
             Output('cluster-selected-content', 'style'),
             Output('cluster-info-display-tab', 'children'),
             Output('analysis-tabs', 'active_tab')],
            [Input('cluster-plot', 'clickData')],
            [State('algorithm-dropdown', 'value')],
            prevent_initial_call=True
        )
        def handle_cluster_click(clickData, algorithm):
            """Handle cluster point clicks and show in cluster analysis tab"""
            if not clickData or not clickData.get('points'):
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update
            point = clickData['points'][0]
            
            # Get the trace index and look up the actual trace name
            curve_number = point.get('curveNumber', 0)
            
            # We need to check if this is from individual tile cluster data
            if 'customdata' in point and point['customdata']:
                customdata = point.get('customdata', [])
                customdata = [customdata] if not isinstance(customdata, list) else customdata

                # Check if this looks like cluster data (has SNR and redshift)
                if len(customdata) >= 2:
                    # Extract cluster information from clicked point
                    ra = point.get('x', 'N/A')
                    dec = point.get('y', 'N/A')
                    snr = round(customdata[0], 2) if len(customdata) > 0 else 'N/A'
                    redshift = round(customdata[1], 2) if len(customdata) > 1 else 'N/A'
                    
                    # Get trace name from hover text or use curve number
                    trace_name = f"Curve {curve_number}"
                    if 'text' in point and point['text']:
                        # Try to extract trace name from hover text
                        text = point['text']
                        if 'Tile' in str(text):
                            trace_name = "Individual Tile Cluster"
                    
                    # Store selected cluster data for use in action callbacks
                    self.selected_cluster = {
                        'ra': ra,
                        'dec': dec,
                        'snr': snr,
                        'redshift': redshift,
                        'algorithm': algorithm,
                        'trace_name': trace_name,
                        'curve_number': curve_number,
                        'point_data': point
                    }
                    
                    print(f"🎯 Cluster clicked: RA={ra:.4f}, Dec={dec:.4f}, SNR={snr}, z={redshift}")
                    
                    # Create tab content with cluster information
                    tab_content = [
                        dbc.Row([
                            dbc.Col([
                                html.Strong("Coordinates", className="text-primary"),
                                html.Div([
                                    f"RA: {ra:.6f}°",
                                    html.Br(),
                                    f"Dec: {dec:.6f}°"
                                ], className="mt-1")
                            ], width=6),
                            dbc.Col([
                                html.Strong("Properties", className="text-primary"),
                                html.Div([
                                    f"SNR: {snr}",
                                    html.Br(),
                                    f"z: {redshift}"
                                ], className="mt-1")
                            ], width=6)
                        ]),
                        html.Hr(className="my-2"),
                        html.Div([
                            html.Strong("Source: ", className="text-primary"),
                            f"{algorithm} | {trace_name}"
                        ])
                    ]
                    
                    # Hide no-selection, show selected content, populate info, switch to cluster tab
                    return (
                        {'display': 'none'},  # Hide no-selection
                        {'display': 'block'},  # Show selected content
                        tab_content,  # Populate cluster info
                        'cluster-tab'  # Switch to cluster tab
                    )
            
            # If clicked point is not a valid cluster, don't change anything
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    def _setup_modal_close_callbacks(self):
        """Setup callbacks to close the modal"""
        @self.app.callback(
            Output('cluster-action-modal', 'is_open', allow_duplicate=True),
            [Input('cluster-modal-close', 'n_clicks'),
             Input('cluster-modal-close-footer', 'n_clicks')],
            [State('cluster-action-modal', 'is_open')],
            prevent_initial_call=True
        )
        def close_modal(close_clicks, footer_clicks, is_open):
            """Close the modal when close buttons are clicked"""
            if close_clicks or footer_clicks:
                return False
            return dash.no_update
    
    def _setup_cutout_toggle_callback(self):
        """Setup callback to toggle cutout options"""
        @self.app.callback(
            Output('cutout-options-collapse', 'is_open'),
            [Input('cluster-cutout-button', 'n_clicks')],
            [State('cutout-options-collapse', 'is_open')],
            prevent_initial_call=True
        )
        def toggle_cutout_options(n_clicks, is_open):
            """Toggle cutout options when cutout button is clicked"""
            if n_clicks:
                return not is_open
            return is_open
    
    def _setup_catred_visibility_callback(self):
        @self.app.callback(
            Output('catred-box-options-collapse', 'is_open'),
            [Input('cluster-catred-box-button', 'n_clicks')],
            [State('catred-box-options-collapse', 'is_open')],
            prevent_initial_call=True
        )
        def toggle_catred_box_options(n_clicks, is_open):
            """Toggle catred box options when catred box button is clicked"""
            if n_clicks:
                return not is_open
            return is_open

    def _setup_action_callbacks(self):
        """Setup callbacks for cluster action buttons"""
        @self.app.callback(
            Output('status-info', 'children', allow_duplicate=True),
            [Input('cluster-cutout-button', 'n_clicks'),
             Input('cluster-phz-button', 'n_clicks'),
             Input('cluster-catred-box-button', 'n_clicks'),
             Input('cluster-export-button', 'n_clicks')],
            [State('cutout-size-input', 'value'),
             State('cutout-data-type', 'value')],
            prevent_initial_call=True
        )
        def handle_cluster_actions(cutout_clicks, phz_clicks, catred_box_clicks, export_clicks, 
                                   cutout_size, cutout_type):
            """Handle various cluster action button clicks"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if not self.selected_cluster:
                return dbc.Alert("⚠️ No cluster selected", color="warning")
            
            cluster = self.selected_cluster

            if button_id == 'cluster-cutout-button':
                # Placeholder for cutout generation
                status_msg = dbc.Alert([
                    html.H6("🔬 Cutout Generation Requested", className="mb-2"),
                    html.P([
                        f"📍 Target: RA {cluster['ra']:.6f}°, Dec {cluster['dec']:.6f}°",
                        html.Br(),
                        f"📏 Size: {cutout_size} arcmin",
                        html.Br(),
                        f"📊 Type: {cutout_type.title()} data",
                        html.Br(),
                        f"🎯 Algorithm: {cluster['algorithm']}"
                    ]),
                    html.Small("Cutout generation functionality will be implemented here", 
                             className="text-muted")
                ], color="info")

                print(f"🔬 Cutout requested: RA={cluster['ra']}, Dec={cluster['dec']}, Size={cutout_size}arcmin, Type={cutout_type}")
                return status_msg
                
            elif button_id == 'cluster-phz-button':
                # Placeholder for PHZ analysis
                status_msg = dbc.Alert([
                    html.H6("📈 PHZ Analysis Requested", className="mb-2"),
                    html.P([
                        f"🎯 Target: RA {cluster['ra']:.6f}°, Dec {cluster['dec']:.6f}°",
                        html.Br(),
                        f"🔢 Current z: {cluster['redshift']}",
                        html.Br(),
                        f"📊 SNR: {cluster['snr']}"
                    ]),
                    html.Small("Photometric redshift analysis will be implemented here", 
                             className="text-muted")
                ], color="success")
                
                print(f"📈 PHZ analysis requested for cluster at RA={cluster['ra']}, Dec={cluster['dec']}")
                return status_msg

            elif button_id == 'cluster-catred-box-button':
                # Placeholder for CATRED box viewing
                status_msg = dbc.Alert([
                    html.H6("🖼️ CATRED Box Requested", className="mb-2"),
                    html.P([
                        f"📍 Target: RA {cluster['ra']:.6f}°, Dec {cluster['dec']:.6f}°, z {cluster['redshift']:.6f}",
                        html.Br(),
                        f"🔍 Algorithm: {cluster['algorithm']}"
                    ]),
                    html.Small("CATRED box functionality will be implemented here", 
                               className="text-muted")
                ], color="primary")

                print(f"🖼️ CATRED box requested for cluster at RA={cluster['ra']}, Dec={cluster['dec']}")
                return status_msg
                
            elif button_id == 'cluster-export-button':
                # Placeholder for data export
                status_msg = dbc.Alert([
                    html.H6("💾 Data Export Requested", className="mb-2"),
                    html.P([
                        f"📍 Target: RA {cluster['ra']:.6f}°, Dec {cluster['dec']:.6f}°",
                        html.Br(),
                        f"📊 Data: SNR={cluster['snr']}, z={cluster['redshift']}"
                    ]),
                    html.Small("Data export functionality will be implemented here", 
                             className="text-muted")
                ], color="warning")
                
                print(f"💾 Data export requested for cluster at RA={cluster['ra']}, Dec={cluster['dec']}")
                return status_msg
            
            return dash.no_update
    
    def _setup_sidebar_callbacks(self):
        """Setup sidebar-specific callbacks"""
        # Toggle cutout options in sidebar
        @self.app.callback(
            Output('sidebar-cutout-options', 'is_open'),
            [Input('quick-cutout-button', 'n_clicks')],
            [State('sidebar-cutout-options', 'is_open')],
            prevent_initial_call=True
        )
        def toggle_sidebar_cutout_options(n_clicks, is_open):
            """Toggle sidebar cutout options"""
            if n_clicks:
                return not is_open
            return is_open
        
        # Toggle CATRED box options in sidebar
        @self.app.callback(
            Output('sidebar-catred-box-options', 'is_open'),
            [Input('quick-catred-box-button', 'n_clicks')],
            [State('sidebar-catred-box-options', 'is_open')],
            prevent_initial_call=True
        )
        def toggle_sidebar_catred_box_options(n_clicks, is_open):
            """Toggle sidebar CATRED box options"""
            if n_clicks:
                return not is_open
            return is_open
        
        # Handle sidebar action buttons
        @self.app.callback(
            Output('status-info', 'children', allow_duplicate=True),
            [Input('sidebar-generate-cutout', 'n_clicks'),
             Input('quick-phz-button', 'n_clicks'),
             Input('quick-catred-box-button', 'n_clicks'),
             Input('cluster-more-options-button', 'n_clicks')],
            [State('sidebar-cutout-size', 'value'),
             State('sidebar-cutout-type', 'value')],
            prevent_initial_call=True
        )
        def handle_sidebar_actions(cutout_clicks, phz_clicks, catred_box_clicks, more_clicks,
                                   cutout_size, cutout_type):
            """Handle sidebar action button clicks"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if not self.selected_cluster:
                return dbc.Alert("⚠️ No cluster selected", color="warning")
            
            cluster = self.selected_cluster
            
            if button_id == 'sidebar-generate-cutout':
                status_msg = dbc.Alert([
                    html.H6("🔬 Generating Cutout...", className="mb-2"),
                    html.P([
                        f"📍 RA {cluster['ra']:.6f}°, Dec {cluster['dec']:.6f}°",
                        html.Br(),
                        f"📏 {cutout_size} arcmin | 📊 {cutout_type.title()}"
                    ]),
                    html.Small("Cutout generation in progress...", className="text-muted")
                ], color="info")
                
                print(f"🔬 Sidebar cutout: RA={cluster['ra']}, Dec={cluster['dec']}, Size={cutout_size}, Type={cutout_type}")
                return status_msg
                
            elif button_id == 'quick-phz-button':
                status_msg = dbc.Alert([
                    html.H6("📈 PHZ Analysis", className="mb-2"),
                    html.P(f"🎯 z={cluster['redshift']} | SNR={cluster['snr']}")
                ], color="success")
                return status_msg
                
            elif button_id == 'quick-catred-box-button':
                status_msg = dbc.Alert([
                    html.H6("🖼️ Loading CATRED Box...", className="mb-2"),
                    html.P(f"📍 RA {cluster['ra']:.4f}°, Dec {cluster['dec']:.4f}°")
                ], color="primary")
                return status_msg
                
            elif button_id == 'cluster-more-options-button':
                # This could open the full modal for advanced options
                status_msg = dbc.Alert([
                    html.H6("⚙️ More Options", className="mb-2"),
                    html.P("Advanced analysis options available")
                ], color="secondary")
                return status_msg
            
            return dash.no_update
    
    def _setup_tab_callbacks(self):
        """Setup tab switching and tab-specific callbacks"""
        # Tab content switching
        @self.app.callback(
            [Output('phz-tab-content', 'style'),
             Output('cluster-tab-content', 'style')],
            [Input('analysis-tabs', 'active_tab')],
            prevent_initial_call=True
        )
        def switch_tab_content(active_tab):
            """Switch between PHZ and cluster analysis tab content"""
            if active_tab == 'phz-tab':
                return {'display': 'block'}, {'display': 'none'}
            elif active_tab == 'cluster-tab':
                return {'display': 'none'}, {'display': 'block'}
            return dash.no_update, dash.no_update
        
        # Toggle cutout options in tab
        @self.app.callback(
            Output('tab-cutout-options', 'is_open'),
            [Input('tab-cutout-button', 'n_clicks')],
            [State('tab-cutout-options', 'is_open')],
            prevent_initial_call=True
        )
        def toggle_tab_cutout_options(n_clicks, is_open):
            """Toggle tab cutout options"""
            if n_clicks:
                return not is_open
            return is_open
        
        # Toggle CATRED box options in tab
        @self.app.callback(
            Output('tab-catred-box-options', 'is_open'),
            [Input('tab-catred-box-button', 'n_clicks')],
            [State('tab-catred-box-options', 'is_open')],
            prevent_initial_call=True
        )
        def toggle_tab_catred_box_options(n_clicks, is_open):
            """Toggle tab CATRED box options"""
            if n_clicks:
                return not is_open
            return is_open
        
        # Handle tab action buttons
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), 
             Output('phz-pdf-plot', 'figure', allow_duplicate=True),
             Output('cluster-analysis-results', 'children'),
             Output('status-info', 'children', allow_duplicate=True)],
            [Input('tab-generate-cutout', 'n_clicks'),
             Input('tab-phz-button', 'n_clicks'),
             Input('tab-view-catred-box', 'n_clicks'),
             Input('tab-export-button', 'n_clicks')],
            [State('algorithm-dropdown', 'value'),
             State('snr-range-slider', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('merged-clusters-switch', 'value'),
             State('tab-cutout-size', 'value'),
             State('tab-cutout-type', 'value'),
             State('tab-catred-box-size', 'value'),
             State('tab-catred-redshift-bin-width', 'value'),
             State('tab-catred-mask-threshold', 'value'),
             State('tab-catred-maglim', 'value'),
             State('catred-mode-switch', 'value'),
             State('catred-threshold-slider', 'value'),
             State('magnitude-limit-slider', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def handle_tab_actions(cutout_clicks, phz_clicks, catred_box_clicks, export_clicks,
                               algorithm, snr_range, show_polygons, show_mer_tiles, free_aspect_ratio, show_merged_clusters,
                               cutout_size, cutout_type, catred_box_size, catred_redshift_bin_width, catred_mask_threshold, catred_maglim,
                               catred_masked, threshold, maglim, relayout_data, current_figure):
            """Handle tab action button clicks"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if not self.selected_cluster:
                return (
                    html.P("⚠️ No cluster selected", className="text-warning"),
                    dbc.Alert("⚠️ No cluster selected", color="warning")
                )
            
            cluster = self.selected_cluster
            
            if button_id == 'tab-generate-cutout':
                # Analysis results for the tab
                results_content = dbc.Card([
                    dbc.CardHeader([
                        html.H6([html.I(className="fas fa-crop me-2"), "Cutout Generation"], className="mb-0 text-primary")
                    ]),
                    dbc.CardBody([
                        html.P([
                            html.Strong("Target: "), f"RA {cluster['ra']:.6f}°, Dec {cluster['dec']:.6f}°",
                            html.Br(),
                            html.Strong("Size: "), f"{cutout_size} arcmin",
                            html.Br(),
                            html.Strong("Type: "), cutout_type.title(),
                            html.Br(),
                            html.Strong("Status: "), html.Span("In Progress...", className="text-info")
                        ])
                    ])
                ])
                
                # Status message
                status_msg = dbc.Alert([
                    html.H6("🔬 Generating Cutout...", className="mb-2"),
                    html.P(f"📍 RA {cluster['ra']:.6f}°, Dec {cluster['dec']:.6f}° | 📏 {cutout_size} arcmin")
                ], color="info")
                
                print(f"🔬 Tab cutout: RA={cluster['ra']}, Dec={cluster['dec']}, Size={cutout_size}, Type={cutout_type}")
                return dash.no_update, dash.no_update, results_content, status_msg

            elif button_id == 'tab-phz-button':
                results_content = dbc.Card([
                    dbc.CardHeader([
                        html.H6([html.I(className="fas fa-chart-line me-2"), "PHZ Analysis"], className="mb-0 text-success")
                    ]),
                    dbc.CardBody([
                        html.P([
                            html.Strong("Current z: "), f"{cluster['redshift']}",
                            html.Br(),
                            html.Strong("SNR: "), f"{cluster['snr']}",
                            html.Br(),
                            html.Strong("Status: "), html.Span("Analysis Complete", className="text-success")
                        ])
                    ])
                ])
                
                status_msg = dbc.Alert([
                    html.H6("📈 PHZ Analysis Complete", className="mb-2"),
                    html.P(f"🎯 z={cluster['redshift']} | SNR={cluster['snr']}")
                ], color="success")

                return dash.no_update, dash.no_update, results_content, status_msg

            elif button_id == 'tab-view-catred-box':
                results_content = dbc.Card([
                    dbc.CardHeader([
                        html.H6([html.I(className="fas fa-magnifying-glass me-2"), "CATRED Box View"], className="mb-0 text-primary")
                    ]),
                    dbc.CardBody([
                        html.P([
                            html.Strong("Target: "), f"RA {cluster['ra']:.4f}°, Dec {cluster['dec']:.4f}°",
                            html.Br(),
                            html.Strong("Box Size: "), f"{catred_box_size} arcmin",
                            html.Br(),
                            html.Strong("Redshift Bin Width: "), f"{catred_redshift_bin_width}",
                            html.Br(),
                            html.Strong("Status: "), html.Span("Loading CATRED Box...", className="text-info")
                        ])
                    ])
                ])

                # Extract SNR values from range slider
                snr_lower = snr_range[0] if snr_range and len(snr_range) == 2 else None
                snr_upper = snr_range[1] if snr_range and len(snr_range) == 2 else None

                # Extract existing CATRED traces from current figure to preserve them
                existing_catred_traces = self._extract_existing_catred_traces(current_figure)

                # Load CATRED Box data
                box_params = self.catred_handler._extract_box_data_from_cluster_click(
                    click_data={'ra': cluster['ra'], 'dec': cluster['dec'],
                                'redshift': cluster['redshift'],
                                'catred_box_size': catred_box_size/60,  # Convert arcmin to degrees
                                'catred_redshift_bin_width': catred_redshift_bin_width}
                )

                data = self.data_loader.load_data(select_algorithm=algorithm)
                catred_box_data = self.catred_handler.load_catred_data_clusterbox(
                    box=box_params, data=data,
                    threshold=catred_mask_threshold, maglim=catred_maglim
                    )

                if self.trace_creator:
                    traces = self.trace_creator.create_traces(
                        data, show_polygons, show_mer_tiles, relayout_data, catred_masked, 
                        catred_box_data=catred_box_data, 
                        existing_catred_traces=existing_catred_traces,
                        snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper, 
                        threshold=catred_mask_threshold, show_merged_clusters=show_merged_clusters
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

                empty_phz_fig = self._create_empty_phz_plot()

                status_msg = dbc.Alert([
                    html.H6("🖼️ Loading CATRED Box...", className="mb-2"),
                    html.P(f"📍 RA {cluster['ra']:.4f}°, Dec {cluster['dec']:.4f}°")
                ], color="primary")

                return fig, empty_phz_fig, results_content, status_msg

            elif button_id == 'tab-export-button':
                results_content = dbc.Card([
                    dbc.CardHeader([
                        html.H6([html.I(className="fas fa-download me-2"), "Data Export"], className="mb-0 text-warning")
                    ]),
                    dbc.CardBody([
                        html.P([
                            html.Strong("Data: "), f"RA={cluster['ra']:.6f}, Dec={cluster['dec']:.6f}, SNR={cluster['snr']}, z={cluster['redshift']}",
                            html.Br(),
                            html.Strong("Format: "), "CSV/JSON",
                            html.Br(),
                            html.Strong("Status: "), html.Span("Ready for Download", className="text-success")
                        ])
                    ])
                ])
                
                status_msg = dbc.Alert([
                    html.H6("💾 Data Export Ready", className="mb-2"),
                    html.P(f"📊 Cluster data prepared for download")
                ], color="warning")

                return dash.no_update, dash.no_update, results_content, status_msg

            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    def _extract_existing_catred_traces(self, current_figure):
        """Extract existing CATRED traces from current figure"""
        existing_catred_traces = []
        if current_figure and 'data' in current_figure:
            for trace in current_figure['data']:
                if (isinstance(trace, dict) and 'name' in trace and trace['name'] and
                    ('CATRED' in trace['name'] or 'CATRED Tiles High-Res Data' in trace['name'])):
                    # Convert dict to Scattergl object for consistency
                    existing_trace = go.Scattergl(
                        x=trace.get('x', []),
                        y=trace.get('y', []),
                        mode=trace.get('mode', 'markers'),
                        marker=trace.get('marker', {}),
                        name=trace.get('name', 'CATRED Data'),
                        text=trace.get('text', []),
                        hoverinfo=trace.get('hoverinfo', 'text'),
                        showlegend=trace.get('showlegend', True)
                    )
                    existing_catred_traces.append(existing_trace)
                    print(f"Debug: Preserved existing CATRED trace: {trace['name']}")
        return existing_catred_traces
    

    def _create_fallback_figure(self, traces, algorithm, free_aspect_ratio):
        """Fallback figure creation method"""
        fig = go.Figure(traces)
        
        # Configure aspect ratio based on setting
        if free_aspect_ratio:
            xaxis_config = dict(visible=True, autorange='reversed')  # Reverse RA axis for astronomy convention
            yaxis_config = dict(visible=True)
        else:
            xaxis_config = dict(
                scaleanchor="y",
                scaleratio=1,
                constrain="domain",
                visible=True,
                autorange='reversed'  # Reverse RA axis for astronomy convention
            )
            yaxis_config = dict(
                constrain="domain",
                visible=True
            )
        
        fig.update_layout(
            title=f'Cluster Detection Visualization - {algorithm}',
            xaxis_title='Right Ascension (degrees)',
            yaxis_title='Declination (degrees)',
            legend=dict(
                title='Legend',
                orientation='v',
                xanchor='left',
                x=1.01,
                yanchor='top',
                y=1,
                font=dict(size=10)
            ),
            hovermode='closest',
            margin=dict(l=40, r=120, t=60, b=40),
            xaxis=xaxis_config,
            yaxis=yaxis_config,
            autosize=True
        )
        
        return fig
    
    def _create_empty_phz_plot(self, message="Click on a CATRED data point to view its PHZ_PDF"):
        """Create empty PHZ_PDF plot with message"""
        empty_phz_fig = go.Figure()
        empty_phz_fig.update_layout(
            title='PHZ_PDF Plot',
            xaxis_title='Redshift',
            yaxis_title='Probability Density',
            margin=dict(l=40, r=20, t=40, b=40),
            showlegend=False,
            annotations=[
                dict(
                    text=message,
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, xanchor='center', yanchor='middle',
                    showarrow=False,
                    font=dict(size=14, color="gray")
                )
            ]
        )
        return empty_phz_fig
    
    def _preserve_zoom_state_fallback(self, fig, relayout_data):
        """Fallback zoom state preservation method"""
        if relayout_data:
            if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                fig.update_xaxes(range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']],
                                 autorange=False)
            elif 'xaxis.range' in relayout_data:
                fig.update_xaxes(range=relayout_data['xaxis.range'], autorange=False)
                
            if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                fig.update_yaxes(range=[relayout_data['yaxis.range[0]'], relayout_data['yaxis.range[1]']])
            elif 'yaxis.range' in relayout_data:
                fig.update_yaxes(range=relayout_data['yaxis.range'])

    def _setup_parameter_sync_callbacks(self):
        """Setup callbacks to sync parameters between tab inputs and sliders"""
        
        # Bidirectional sync for magnitude limit
        @self.app.callback(
            [Output('magnitude-limit-slider', 'value', allow_duplicate=True),
            Output('tab-catred-maglim', 'value', allow_duplicate=True)],
            [Input('magnitude-limit-slider', 'value'),
            Input('tab-catred-maglim', 'value')],
            prevent_initial_call=True
        )
        def sync_magnitude_limit_bidirectional(slider_value, tab_value):
            """Bidirectionally sync magnitude limit between slider and tab input"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update
                
            triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if triggered_id == 'magnitude-limit-slider' and slider_value is not None:
                # Slider changed, update tab input
                return dash.no_update, slider_value
            elif triggered_id == 'tab-catred-maglim' and tab_value is not None:
                # Tab input changed, update slider
                return tab_value, dash.no_update
                
            return dash.no_update, dash.no_update
        
        # Bidirectional sync for threshold
        @self.app.callback(
            [Output('catred-threshold-slider', 'value', allow_duplicate=True),
            Output('tab-catred-mask-threshold', 'value', allow_duplicate=True)],
            [Input('catred-threshold-slider', 'value'),
            Input('tab-catred-mask-threshold', 'value')],
            prevent_initial_call=True
        )
        def sync_threshold_bidirectional(slider_value, tab_value):
            """Bidirectionally sync threshold between slider and tab input"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update
                
            triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if triggered_id == 'catred-threshold-slider' and slider_value is not None:
                # Slider changed, update tab input
                return dash.no_update, slider_value
            elif triggered_id == 'tab-catred-mask-threshold' and tab_value is not None:
                # Tab input changed, update slider
                return tab_value, dash.no_update
                
            return dash.no_update, dash.no_update