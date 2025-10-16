"""
Main plot callbacks for cluster visualization.

Handles primary rendering logic for the main cluster visualization plot,
including initial rendering, real-time option updates, and SNR filtering.
"""

import dash
from dash import Input, Output, State, html
import plotly.graph_objs as go
import pandas as pd
import dash_bootstrap_components as dbc


class MainPlotCallbacks:
    """Handles main plot rendering callbacks"""
    
    def __init__(self, app, data_loader, catred_handler, trace_creator, figure_manager, mosaic_handler=None):
        """
        Initialize main plot callbacks.
        
        Args:
            app: Dash application instance
            data_loader: DataLoader instance for data operations
            catred_handler: CATREDHandler instance for CATRED operations
            trace_creator: TraceCreator instance for trace creation
            figure_manager: FigureManager instance for figure layout
            mosaic_handler: MOSAICHandler instance for mosaic operations
        """
        self.app = app
        self.data_loader = data_loader
        self.catred_handler = catred_handler
        self.trace_creator = trace_creator
        self.figure_manager = figure_manager
        self.mosaic_handler = mosaic_handler
        
        # Fallback attributes for backward compatibility
        self.data_cache = {}
        self.catred_traces_cache = []
        self.current_catred_data = None
        
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """Setup all main plot callbacks"""
        self._setup_snr_slider_callback()
        self._setup_redshift_slider_callback()
        self._setup_main_render_callback()
        self._setup_options_update_callback()
        self._setup_threshold_clientside_callback()
        self._setup_snr_clientside_callback()
        self._setup_redshift_clientside_callback()
        self._setup_mosaic_render_callback()
    
    def _setup_snr_slider_callback(self):
        """Setup SNR slider initialization callback"""
        @self.app.callback(
            [Output('snr-range-slider', 'min'),
             Output('snr-range-slider', 'max'),
             Output('snr-range-slider', 'value'),
             Output('snr-range-slider', 'marks'),
             Output('snr-range-display', 'children')],
            [Input('algorithm-dropdown', 'value')],
            prevent_initial_call=False
        )
        def update_snr_slider(algorithm):
            try:
                # Load data to get SNR range
                data = self.load_data(algorithm)
                snr_min = data['snr_min']
                snr_max = data['snr_max']
                
                # Create marks at key points
                marks = {
                    snr_min: f'{snr_min:.1f}',
                    snr_max: f'{snr_max:.1f}'
                }
                
                # Default to full range
                default_value = [snr_min, snr_max]
                
                display_text = html.Div([
                    html.Small(f"SNR Range: {snr_min:.2f} to {snr_max:.2f}", className="text-muted"),
                    html.Small(" | Move sliders to set filter range", className="text-muted")
                ])
                
                return snr_min, snr_max, default_value, marks, display_text
                
            except Exception as e:
                # Fallback values if data loading fails
                return 0, 100, [0, 100], {0: '0', 100: '100'}, html.Small("SNR data not available", className="text-muted")
    
    def _setup_redshift_slider_callback(self):
        """Setup redshift slider initialization callback"""
        @self.app.callback(
            [Output('redshift-range-slider', 'min'),
             Output('redshift-range-slider', 'max'),
             Output('redshift-range-slider', 'value'),
             Output('redshift-range-slider', 'marks'),
             Output('redshift-range-display', 'children')],
            [Input('algorithm-dropdown', 'value')],
            prevent_initial_call=False
        )
        def update_redshift_slider(algorithm):
            try:
                # Load data to get redshift range
                data = self.load_data(algorithm)
                z_min = data['z_min']
                z_max = data['z_max']

                # Create marks at key points
                marks = {
                    z_min: f'{z_min:.1f}',
                    z_max: f'{z_max:.1f}'
                }
                
                # Default to full range
                default_value = [z_min, z_max]

                display_text = html.Div([
                    html.Small(f"Redshift Range: {z_min:.2f} to {z_max:.2f}", className="text-muted"),
                    html.Small(" | Move sliders to set filter range", className="text-muted")
                ])

                return z_min, z_max, default_value, marks, display_text

            except Exception as e:
                # Fallback values if data loading fails
                return 0, 10, [0, 10], {0: '0', 10: '10'}, html.Small("Redshift data not available", className="text-muted")

    def _setup_main_render_callback(self):
        """Setup main rendering callback for initial and SNR-filtered renders"""
        @self.app.callback(
            [Output('cluster-plot', 'figure'), 
             Output('phz-pdf-plot', 'figure'), 
             Output('status-info', 'children')
             ],
            [Input('render-button', 'n_clicks'), 
             Input('snr-render-button', 'n_clicks'), 
             Input('redshift-render-button', 'n_clicks')
             ],
            [State('algorithm-dropdown', 'value'),
             State('snr-range-slider', 'value'),
             State('redshift-range-slider', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mode-switch', 'value'),
             State('catred-threshold-slider', 'value'),
             State('magnitude-limit-slider', 'value'),
             State('cluster-plot', 'relayoutData')
             ]
        )
        def update_plot(n_clicks, snr_n_clicks, redshift_n_clicks, algorithm, 
                        snr_range, redshift_range, show_polygons, show_mer_tiles, 
                        free_aspect_ratio, catred_mode, threshold, maglim, relayout_data):
            # Only render if button has been clicked at least once
            if n_clicks == 0 and snr_n_clicks == 0 and redshift_n_clicks == 0:
                return self._create_initial_empty_plots(free_aspect_ratio)
            
            try:
                # Extract SNR values from range slider
                snr_lower = snr_range[0] if snr_range and len(snr_range) == 2 else None
                snr_upper = snr_range[1] if snr_range and len(snr_range) == 2 else None
                
                # Extract redshift values from range slider
                z_lower = redshift_range[0] if redshift_range and len(redshift_range) == 2 else None
                z_upper = redshift_range[1] if redshift_range and len(redshift_range) == 2 else None

                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Only reset CATRED traces cache if algorithm changed, not for SNR/redshift filtering
                # CATRED data doesn't have SNR and shouldn't be affected by cluster-level filtering
                # Note: This preserves CATRED data when only SNR/redshift filters change
                
                # Create traces
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, catred_mode, 
                                            snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper, 
                                            z_threshold_lower=z_lower, z_threshold_upper=z_upper, 
                                            threshold=threshold, maglim=maglim)

                # Create figure
                fig = self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio) if self.figure_manager else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                
                # Preserve zoom state if available
                if self.figure_manager:
                    self.figure_manager.preserve_zoom_state(fig, relayout_data)
                else:
                    self._preserve_zoom_state_fallback(fig, relayout_data)
                
                # Calculate filtered cluster counts for status
                filtered_merged_count = self._calculate_filtered_count(data['data_detcluster_mergedcat'], snr_lower, snr_upper, z_lower, z_upper)
                
                # Create status info
                status = self._create_status_info(algorithm, data, filtered_merged_count, snr_lower, snr_upper, 
                                                z_lower, z_upper, show_polygons, show_mer_tiles, free_aspect_ratio, "success")
                
                # Create empty PHZ_PDF plot
                empty_phz_fig = self._create_empty_phz_plot()
                
                return fig, empty_phz_fig, status
                
            except Exception as e:
                return self._create_error_plots(str(e))
    
    def _setup_options_update_callback(self):
        """Setup real-time options update callback (preserves zoom)"""
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), 
             Output('phz-pdf-plot', 'figure', allow_duplicate=True), 
             Output('status-info', 'children', allow_duplicate=True)],
            [Input('algorithm-dropdown', 'value'),
             Input('polygon-switch', 'value'),
             Input('mer-switch', 'value'),
             Input('aspect-ratio-switch', 'value'),
             Input('catred-mode-switch', 'value')],
            [State('render-button', 'n_clicks'),
             State('snr-range-slider', 'value'),
             State('redshift-range-slider', 'value'),
             State('catred-threshold-slider', 'value'),
             State('magnitude-limit-slider', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def update_plot_options(algorithm, show_polygons, show_mer_tiles, free_aspect_ratio, catred_mode, n_clicks, snr_range, redshift_range, threshold, maglim, relayout_data, current_figure):
            # Only update if render button has been clicked at least once
            if n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update
            
            try:
                # Extract SNR values from range slider
                snr_lower = snr_range[0] if snr_range and len(snr_range) == 2 else None
                snr_upper = snr_range[1] if snr_range and len(snr_range) == 2 else None
                
                # Extract redshift values from range slider
                z_lower = redshift_range[0] if redshift_range and len(redshift_range) == 2 else None
                z_upper = redshift_range[1] if redshift_range and len(redshift_range) == 2 else None

                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Extract existing CATRED traces from current figure to preserve them
                existing_catred_traces = self._extract_existing_catred_traces(current_figure)
                
                print(f"Debug: Options update - preserving {len(existing_catred_traces)} CATRED traces")
                
                # Create traces with existing CATRED traces preserved
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, catred_mode, 
                                            existing_catred_traces=existing_catred_traces, 
                                            snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper, 
                                            z_threshold_lower=z_lower, z_threshold_upper=z_upper,
                                            threshold=threshold, maglim=maglim)
                
                # Create figure
                fig = self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio) if self.figure_manager else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                
                # Preserve zoom state from current figure or relayoutData
                if self.figure_manager:
                    self.figure_manager.preserve_zoom_state(fig, relayout_data, current_figure)
                else:
                    self._preserve_zoom_state_fallback(fig, relayout_data, current_figure)
                
                # Calculate filtered cluster counts for status
                filtered_merged_count = self._calculate_filtered_count(data['data_detcluster_mergedcat'], snr_lower, snr_upper, z_lower, z_upper)

                # Create status info
                status = self._create_status_info(algorithm, data, filtered_merged_count, snr_lower, snr_upper, 
                                                z_lower, z_upper, show_polygons, show_mer_tiles, free_aspect_ratio, "info", is_update=True)
                
                # Create empty PHZ_PDF plot
                empty_phz_fig = self._create_empty_phz_plot()
                
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
            Output('cluster-plot', 'figure', allow_duplicate=True),
            [Input('catred-threshold-slider', 'value')],
            [State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
    
    def _setup_snr_clientside_callback(self):
        """Setup client-side SNR filtering callback"""
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
                        
                        // Get current redshift filter from trace if it exists
                        let currentZRange = trace._currentZRange || [0, 999]; // Default wide range
                        
                        for (let j = 0; j < originalData.x.length; j++) {
                            // Get SNR and redshift values
                            let snrValue = originalData.customdata[j] ? originalData.customdata[j][0] : null;
                            let zValue = originalData.customdata[j] ? originalData.customdata[j][1] : null;
                            
                            // Apply both SNR and redshift filters together
                            let passesSnrFilter = (snrValue !== null && snrValue !== undefined && 
                                                 snrValue >= snrLower && snrValue <= snrUpper);
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
            Output('cluster-plot', 'figure', allow_duplicate=True),
            [Input('snr-range-slider', 'value')],
            [State('cluster-plot', 'figure')],
            prevent_initial_call=True
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
            Output('cluster-plot', 'figure', allow_duplicate=True),
            [Input('redshift-range-slider', 'value')],
            [State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
    
    def load_data(self, algorithm):
        """Load data using modular or fallback method"""
        if self.data_loader:
            return self.data_loader.load_data(algorithm)
        else:
            # Fallback to inline data loading
            return self._load_data_fallback(algorithm)
    
    def create_traces(self, data, show_polygons, show_mer_tiles, relayout_data, catred_mode, 
                     existing_catred_traces=None, manual_catred_data=None, 
                     snr_threshold_lower=None, snr_threshold_upper=None, 
                     z_threshold_lower=None, z_threshold_upper=None, 
                     threshold=0.8, maglim=None):
        """Create traces using modular or fallback method"""
        if self.trace_creator:
            return self.trace_creator.create_traces(
                data, show_polygons, show_mer_tiles, relayout_data, catred_mode,
                existing_catred_traces=existing_catred_traces, manual_catred_data=manual_catred_data,
                snr_threshold_lower=snr_threshold_lower, snr_threshold_upper=snr_threshold_upper, 
                z_threshold_lower=z_threshold_lower, z_threshold_upper=z_threshold_upper, 
                threshold=threshold, maglim=maglim
            )
        else:
            # Fallback to inline trace creation
            return self._create_traces_fallback(data, show_polygons, show_mer_tiles, relayout_data, catred_mode,
                                              existing_mer_traces=existing_catred_traces, manual_mer_data=manual_catred_data,
                                              snr_threshold_lower=snr_threshold_lower, snr_threshold_upper=snr_threshold_upper, 
                                              z_threshold_lower=z_threshold_lower, z_threshold_upper=z_threshold_upper, 
                                              threshold=threshold)

    # Helper methods for fallback and utility functions
    def _create_initial_empty_plots(self, free_aspect_ratio):
        """Create initial empty plots"""
        # Initial empty figure
        initial_fig = go.Figure()
        
        # Configure aspect ratio based on setting
        if free_aspect_ratio:
            xaxis_config = dict(visible=False)
            yaxis_config = dict(visible=False)
        else:
            xaxis_config = dict(
                scaleanchor="y",
                scaleratio=1,
                constrain="domain",
                visible=False
            )
            yaxis_config = dict(
                constrain="domain",
                visible=False
            )
        
        initial_fig.update_layout(
            title='',
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis=xaxis_config,
            yaxis=yaxis_config,
            autosize=True,
            showlegend=False,
            annotations=[
                dict(
                    text="Select your preferred algorithm and display options from the sidebar,<br>then click the 'Initial Render' button to generate the plot.",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, xanchor='center', yanchor='middle',
                    showarrow=False,
                    font=dict(size=16, color="gray")
                )
            ]
        )
        
        # Initial empty PHZ_PDF plot
        initial_phz_fig = self._create_empty_phz_plot("Click on a MER data point above to view its PHZ_PDF")
        
        initial_status = dbc.Alert([
            html.H6("Ready to render", className="mb-1"),
            html.P("Click 'Initial Render' to begin. After that, options will update automatically while preserving your zoom level.", className="mb-0")
        ], color="secondary", className="mt-2")
        
        return initial_fig, initial_phz_fig, initial_status
    
    def _create_empty_phz_plot(self, message="Click on a MER data point to view its PHZ_PDF"):
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
    
    def _create_error_plots(self, error_message):
        """Create error plots for exception handling"""
        error_fig = go.Figure()
        error_fig.add_annotation(
            text=f"Error loading data: {error_message}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False,
            font=dict(size=16, color="red")
        )
        error_fig.update_layout(
            title="Error Loading Visualization",
            margin=dict(l=40, r=120, t=60, b=40),
            autosize=True
        )
        
        error_status = dbc.Alert(f"Error: {error_message}", color="danger")
        error_phz_fig = self._create_empty_phz_plot("Error loading data")
        
        return error_fig, error_phz_fig, error_status
    
    def _extract_existing_catred_traces(self, current_figure):
        """Extract existing CATRED traces from current figure"""
        existing_catred_traces = []
        if current_figure and 'data' in current_figure:
            for trace in current_figure['data']:
                if (isinstance(trace, dict) and 
                    'name' in trace and 
                    trace['name'] and 
                    ('CATRED High-Res Data' in trace['name'] or 'CATRED Tiles High-Res Data' in trace['name'])):
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
        return existing_catred_traces
    
    def _calculate_filtered_count(self, cluster_data, snr_lower, snr_upper, z_lower, z_upper):
        """Calculate filtered cluster count based on SNR range"""
        if snr_lower is None and snr_upper is None:
            cluster_data_1 = cluster_data
        elif snr_lower is not None and snr_upper is not None:
            cluster_data_1 = cluster_data[
                (cluster_data['SNR_CLUSTER'] >= snr_lower) & 
                (cluster_data['SNR_CLUSTER'] <= snr_upper)
                ]
        elif snr_upper is not None and snr_lower is None:
            cluster_data_1 = cluster_data[cluster_data['SNR_CLUSTER'] <= snr_upper]
        elif snr_lower is not None and snr_upper is None:
            cluster_data_1 = cluster_data[cluster_data['SNR_CLUSTER'] >= snr_lower]

        if z_lower is None and z_upper is None:
            return len(cluster_data_1)
        elif z_lower is not None and z_upper is not None:
            return len(cluster_data_1[
                (cluster_data_1['Z_CLUSTER'] >= z_lower) & 
                (cluster_data_1['Z_CLUSTER'] <= z_upper)
                ])
        elif z_upper is not None and z_lower is None:
            return len(cluster_data_1[cluster_data_1['Z_CLUSTER'] <= z_upper])
        elif z_lower is not None and z_upper is None:
            return len(cluster_data_1[cluster_data_1['Z_CLUSTER'] >= z_lower])


    def _create_status_info(self, algorithm, data, filtered_merged_count, snr_lower, snr_upper, 
                           z_lower, z_upper, show_polygons, show_mer_tiles, free_aspect_ratio, alert_color, is_update=False):
        """Create status information display"""
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
        if snr_lower is not None and snr_upper is not None:
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
        
        status = dbc.Alert([
            html.H6(f"Algorithm: {algorithm}", className="mb-1"),
            html.P(f"Merged clusters: {filtered_merged_count}/{len(data['data_detcluster_mergedcat'])} (filtered)", className="mb-1"),
            html.P(f"Individual tiles: {len(data['data_detcluster_by_cltile'])}", className="mb-1"),
            html.P(f"SNR Filter: {snr_filter_text}", className="mb-1"),
            html.P(f"Redshift Filter: {z_filter_text}", className="mb-1"),
            html.P(f"Polygon mode: {'Filled' if show_polygons else 'Outline'}{mer_status}", className="mb-1"),
            html.P(f"Aspect ratio: {aspect_mode}", className="mb-1"),
            html.Small(f"{timestamp_text}: {pd.Timestamp.now().strftime('%H:%M:%S')}", className="text-muted")
        ], color=alert_color, className="mt-2")
        
        return status
    
    # Fallback methods for backward compatibility
    def _load_data_fallback(self, algorithm):
        """Fallback data loading method"""
        # This would contain the original inline data loading logic
        # For now, return empty structure to prevent errors
        return {
            'data_detcluster_mergedcat': pd.DataFrame(),
            'data_detcluster_by_cltile': pd.DataFrame(),
            'snr_min': 0,
            'snr_max': 100,
            'z_min': 0,
            'z_max': 10
        }
    
    def _create_traces_fallback(self, data, show_polygons, show_mer_tiles, relayout_data, catred_mode,
                               existing_mer_traces=None, manual_mer_data=None, snr_threshold_lower=None, snr_threshold_upper=None, threshold=0.8):
        """Fallback trace creation method"""
        # This would contain the original inline trace creation logic
        # For now, return empty traces to prevent errors
        return []
    
    def _create_fallback_figure(self, traces, algorithm, free_aspect_ratio):
        """Fallback figure creation method"""
        fig = go.Figure(traces)
        
        # Configure aspect ratio based on setting
        if free_aspect_ratio:
            xaxis_config = dict(visible=True)
            yaxis_config = dict(visible=True)
        else:
            xaxis_config = dict(
                scaleanchor="y",
                scaleratio=1,
                constrain="domain",
                visible=True
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
    
    def _preserve_zoom_state_fallback(self, fig, relayout_data, current_figure=None):
        """Fallback zoom state preservation method"""
        # Preserve zoom state if available
        if relayout_data and any(key in relayout_data for key in ['xaxis.range[0]', 'xaxis.range[1]', 'yaxis.range[0]', 'yaxis.range[1]']):
            if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                fig.update_xaxes(range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']])
            if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                fig.update_yaxes(range=[relayout_data['yaxis.range[0]'], relayout_data['yaxis.range[1]']])
        elif relayout_data and 'xaxis.range' in relayout_data:
            fig.update_xaxes(range=relayout_data['xaxis.range'])
            if 'yaxis.range' in relayout_data:
                fig.update_yaxes(range=relayout_data['yaxis.range'])
        elif current_figure and 'layout' in current_figure:
            # Fallback: try to preserve from current figure layout
            current_layout = current_figure['layout']
            if 'xaxis' in current_layout and 'range' in current_layout['xaxis']:
                fig.update_xaxes(range=current_layout['xaxis']['range'])
            if 'yaxis' in current_layout and 'range' in current_layout['yaxis']:
                fig.update_yaxes(range=current_layout['yaxis']['range'])

    def _setup_mosaic_render_callback(self):
        """Setup mosaic image rendering callback"""
        print(f"🔧 Setting up mosaic render callback, mosaic_handler: {self.mosaic_handler}")
        if not self.mosaic_handler:
            print("⚠️  Skipping mosaic callback - no mosaic handler available")
            return  # Skip if no mosaic handler available
            
        print("✅ Adding mosaic render callback")
        
        @self.app.callback(
            Output('cluster-plot', 'figure', allow_duplicate=True),
            [Input('mosaic-render-button', 'n_clicks')],
            [State('cluster-plot', 'figure'),
             State('cluster-plot', 'relayoutData'),
             State('mosaic-enable-switch', 'value'),
             State('mosaic-opacity-slider', 'value'),
             State('algorithm-dropdown', 'value')],
            prevent_initial_call=True
        )
        def render_mosaic_images(n_clicks, current_figure, relayout_data, mosaic_enabled, opacity, algorithm):
            """Render mosaic images when button is clicked"""
            try:
                print(f"🔍 Mosaic callback triggered! n_clicks={n_clicks}, mosaic_enabled={mosaic_enabled}")
                print(f"   -> relayout_data keys: {list(relayout_data.keys()) if relayout_data else None}")
                print(f"   -> opacity: {opacity}, algorithm: {algorithm}")
                print(f"   -> current_figure exists: {current_figure is not None}")
                
                if not n_clicks:
                    print(f"   -> Returning early: n_clicks is {n_clicks}")
                    return current_figure
                    
                if not mosaic_enabled:
                    print(f"   -> Returning early: mosaic not enabled ({mosaic_enabled})")
                    return current_figure
                
                print("🚀 Proceeding with mosaic loading...")
                try:
                    print(f"   -> Loading data for algorithm: {algorithm}")
                    # Load current data
                    data = self.data_loader.load_data(algorithm)
                    print(f"   -> Data loaded successfully")
                    
                    # Get mosaic traces for current zoom window
                    if self.mosaic_handler:
                        mosaic_traces = self.mosaic_handler.load_mosaic_traces_in_zoom(data, relayout_data, opacity=opacity)
                        print(f"   -> Mosaic traces result: {len(mosaic_traces) if mosaic_traces else 0} traces")
                        
                        if mosaic_traces and len(mosaic_traces) > 0:
                            # Add mosaic traces to current figure with proper layering
                            if current_figure and 'data' in current_figure:
                                # Remove existing mosaic traces first
                                existing_traces = [trace for trace in current_figure['data'] 
                                                 if not (trace.get('name', '').startswith('Mosaic'))]
                                
                                # Separate traces by type to maintain proper layering order
                                polygon_traces = []
                                catred_traces = []
                                cluster_traces = []
                                other_traces = []
                                
                                for trace in existing_traces:
                                    trace_name = trace.get('name', '')
                                    if 'Tile' in trace_name and ('CORE' in trace_name or 'LEV1' in trace_name or 'MerTile' in trace_name):
                                        polygon_traces.append(trace)
                                    elif 'CATRED' in trace_name or 'MER High-Res Data' in trace_name:
                                        catred_traces.append(trace)
                                    elif any(keyword in trace_name for keyword in ['Merged Data', 'Tile', 'clusters']):
                                        cluster_traces.append(trace)
                                    else:
                                        other_traces.append(trace)
                                
                                # Layer order: polygons (bottom) → mosaic → CATRED → other → cluster traces (top)
                                new_data = polygon_traces + mosaic_traces + catred_traces + other_traces + cluster_traces
                                current_figure['data'] = new_data
                                
                                print(f"✓ Added {len(mosaic_traces)} mosaic image traces as 2nd layer from bottom")
                                print(f"   -> Layer order: {len(polygon_traces)} polygons, {len(mosaic_traces)} mosaics, {len(catred_traces)} CATRED, {len(other_traces)} other, {len(cluster_traces)} clusters (top)")
                            else:
                                print("⚠️  No current figure data to update")
                        else:
                            print("ℹ️  No mosaic images found for current zoom window")
                    else:
                        print("❌ No mosaic handler available")
                    
                    print("   -> Returning updated figure")
                    return current_figure
                    
                except Exception as e:
                    print(f"❌ Error in mosaic loading: {e}")
                    import traceback
                    traceback.print_exc()
                    return current_figure
                    
            except Exception as e:
                print(f"❌ Fatal error in mosaic callback: {e}")
                import traceback
                traceback.print_exc()
                return current_figure
