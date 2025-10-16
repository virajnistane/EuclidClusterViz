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
    
    def __init__(self, app, data_loader, trace_creator, figure_manager):
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
        self._setup_action_callbacks()
        self._setup_tab_callbacks()  # 🆕 Add tab callbacks
    
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
                
                # Check if this looks like cluster data (has SNR and redshift)
                if len(customdata) >= 2:
                    # Extract cluster information from clicked point
                    ra = point.get('x', 'N/A')
                    dec = point.get('y', 'N/A')
                    snr = customdata[0] if len(customdata) > 0 else 'N/A'
                    redshift = customdata[1] if len(customdata) > 1 else 'N/A'
                    
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
    
    def _setup_action_callbacks(self):
        """Setup callbacks for cluster action buttons"""
        @self.app.callback(
            Output('status-info', 'children', allow_duplicate=True),
            [Input('generate-cutout-button', 'n_clicks'),
             Input('cluster-phz-button', 'n_clicks'),
             Input('cluster-images-button', 'n_clicks'),
             Input('cluster-export-button', 'n_clicks')],
            [State('cutout-size-input', 'value'),
             State('cutout-data-type', 'value')],
            prevent_initial_call=True
        )
        def handle_cluster_actions(cutout_clicks, phz_clicks, images_clicks, export_clicks, 
                                 cutout_size, cutout_type):
            """Handle various cluster action button clicks"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if not self.selected_cluster:
                return dbc.Alert("⚠️ No cluster selected", color="warning")
            
            cluster = self.selected_cluster
            
            if button_id == 'generate-cutout-button':
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
                
            elif button_id == 'cluster-images-button':
                # Placeholder for image viewing
                status_msg = dbc.Alert([
                    html.H6("🖼️ Image Viewer Requested", className="mb-2"),
                    html.P([
                        f"📍 Target: RA {cluster['ra']:.6f}°, Dec {cluster['dec']:.6f}°",
                        html.Br(),
                        f"🔍 Algorithm: {cluster['algorithm']}"
                    ]),
                    html.Small("Image viewer functionality will be implemented here", 
                             className="text-muted")
                ], color="primary")
                
                print(f"🖼️ Image viewer requested for cluster at RA={cluster['ra']}, Dec={cluster['dec']}")
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
        
        # Handle sidebar action buttons
        @self.app.callback(
            Output('status-info', 'children', allow_duplicate=True),
            [Input('sidebar-generate-cutout', 'n_clicks'),
             Input('quick-phz-button', 'n_clicks'),
             Input('quick-images-button', 'n_clicks'),
             Input('cluster-more-options-button', 'n_clicks')],
            [State('sidebar-cutout-size', 'value'),
             State('sidebar-cutout-type', 'value')],
            prevent_initial_call=True
        )
        def handle_sidebar_actions(cutout_clicks, phz_clicks, images_clicks, more_clicks,
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
                
            elif button_id == 'quick-images-button':
                status_msg = dbc.Alert([
                    html.H6("🖼️ Loading Images...", className="mb-2"),
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
        
        # Handle tab action buttons
        @self.app.callback(
            [Output('cluster-analysis-results', 'children'),
             Output('status-info', 'children', allow_duplicate=True)],
            [Input('tab-generate-cutout', 'n_clicks'),
             Input('tab-phz-button', 'n_clicks'),
             Input('tab-images-button', 'n_clicks'),
             Input('tab-export-button', 'n_clicks')],
            [State('tab-cutout-size', 'value'),
             State('tab-cutout-type', 'value')],
            prevent_initial_call=True
        )
        def handle_tab_actions(cutout_clicks, phz_clicks, images_clicks, export_clicks,
                              cutout_size, cutout_type):
            """Handle tab action button clicks"""
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update
            
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
                return results_content, status_msg
                
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
                
                return results_content, status_msg
                
            elif button_id == 'tab-images-button':
                results_content = dbc.Card([
                    dbc.CardHeader([
                        html.H6([html.I(className="fas fa-images me-2"), "Image Viewer"], className="mb-0 text-primary")
                    ]),
                    dbc.CardBody([
                        html.P([
                            html.Strong("Target: "), f"RA {cluster['ra']:.4f}°, Dec {cluster['dec']:.4f}°",
                            html.Br(),
                            html.Strong("Status: "), html.Span("Loading Images...", className="text-info")
                        ])
                    ])
                ])
                
                status_msg = dbc.Alert([
                    html.H6("🖼️ Loading Images...", className="mb-2"),
                    html.P(f"📍 RA {cluster['ra']:.4f}°, Dec {cluster['dec']:.4f}°")
                ], color="primary")
                
                return results_content, status_msg
                
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
                
                return results_content, status_msg
            
            return dash.no_update, dash.no_update