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
    
    def __init__(self, app, data_loader, mer_handler, trace_creator, figure_manager):
        """
        Initialize main plot callbacks.
        
        Args:
            app: Dash application instance
            data_loader: DataLoader instance for data operations
            mer_handler: MERHandler instance for MER operations
            trace_creator: TraceCreator instance for trace creation
            figure_manager: FigureManager instance for figure layout
        """
        self.app = app
        self.data_loader = data_loader
        self.mer_handler = mer_handler
        self.trace_creator = trace_creator
        self.figure_manager = figure_manager
        
        # Fallback attributes for backward compatibility
        self.data_cache = {}
        self.mer_traces_cache = []
        self.current_mer_data = None
        
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """Setup all main plot callbacks"""
        self._setup_snr_slider_callback()
        self._setup_main_render_callback()
        self._setup_options_update_callback()
    
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
                    snr_max: f'{snr_max:.1f}',
                    (snr_min + snr_max) / 2: f'{(snr_min + snr_max) / 2:.1f}'
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
    
    def _setup_main_render_callback(self):
        """Setup main rendering callback for initial and SNR-filtered renders"""
        @self.app.callback(
            [Output('cluster-plot', 'figure'), Output('phz-pdf-plot', 'figure'), Output('status-info', 'children')],
            [Input('render-button', 'n_clicks'), Input('snr-render-button', 'n_clicks')],
            [State('algorithm-dropdown', 'value'),
             State('snr-range-slider', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mertile-switch', 'value'),
             State('cluster-plot', 'relayoutData')]
        )
        def update_plot(n_clicks, snr_n_clicks, algorithm, snr_range, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, relayout_data):
            # Only render if button has been clicked at least once
            if n_clicks == 0 and snr_n_clicks == 0:
                return self._create_initial_empty_plots(free_aspect_ratio)
            
            try:
                # Extract SNR values from range slider
                snr_lower = snr_range[0] if snr_range and len(snr_range) == 2 else None
                snr_upper = snr_range[1] if snr_range and len(snr_range) == 2 else None
                
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Reset MER traces cache for fresh render
                if self.mer_handler:
                    self.mer_handler.clear_traces_cache()
                else:
                    self.mer_traces_cache = []
                
                # Create traces
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data, 
                                          snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper)
                
                # Create figure
                fig = self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio) if self.figure_manager else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                
                # Preserve zoom state if available
                if self.figure_manager:
                    self.figure_manager.preserve_zoom_state(fig, relayout_data)
                else:
                    self._preserve_zoom_state_fallback(fig, relayout_data)
                
                # Calculate filtered cluster counts for status
                filtered_merged_count = self._calculate_filtered_count(data['merged_data'], snr_lower, snr_upper)
                
                # Create status info
                status = self._create_status_info(algorithm, data, filtered_merged_count, snr_lower, snr_upper, 
                                                show_polygons, show_mer_tiles, free_aspect_ratio, "success")
                
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
             Input('catred-mertile-switch', 'value')],
            [State('render-button', 'n_clicks'),
             State('snr-range-slider', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def update_plot_options(algorithm, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, n_clicks, snr_range, relayout_data, current_figure):
            # Only update if render button has been clicked at least once
            if n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update
            
            try:
                # Extract SNR values from range slider
                snr_lower = snr_range[0] if snr_range and len(snr_range) == 2 else None
                snr_upper = snr_range[1] if snr_range and len(snr_range) == 2 else None
                
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Extract existing MER traces from current figure to preserve them
                existing_mer_traces = self._extract_existing_mer_traces(current_figure)
                
                print(f"Debug: Options update - preserving {len(existing_mer_traces)} MER traces")
                
                # Create traces with existing MER traces preserved
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data, 
                                          existing_mer_traces=existing_mer_traces, snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper)
                
                # Create figure
                fig = self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio) if self.figure_manager else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                
                # Preserve zoom state from current figure or relayoutData
                if self.figure_manager:
                    self.figure_manager.preserve_zoom_state(fig, relayout_data, current_figure)
                else:
                    self._preserve_zoom_state_fallback(fig, relayout_data, current_figure)
                
                # Calculate filtered cluster counts for status
                filtered_merged_count = self._calculate_filtered_count(data['merged_data'], snr_lower, snr_upper)
                
                # Create status info
                status = self._create_status_info(algorithm, data, filtered_merged_count, snr_lower, snr_upper, 
                                                show_polygons, show_mer_tiles, free_aspect_ratio, "info", is_update=True)
                
                # Create empty PHZ_PDF plot
                empty_phz_fig = self._create_empty_phz_plot()
                
                return fig, empty_phz_fig, status
                
            except Exception as e:
                error_status = dbc.Alert(f"Error updating: {str(e)}", color="warning")
                return dash.no_update, dash.no_update, error_status
    
    def load_data(self, algorithm):
        """Load data using modular or fallback method"""
        if self.data_loader:
            return self.data_loader.load_data(algorithm)
        else:
            # Fallback to inline data loading
            return self._load_data_fallback(algorithm)
    
    def create_traces(self, data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data, 
                     existing_mer_traces=None, manual_mer_data=None, snr_threshold_lower=None, snr_threshold_upper=None):
        """Create traces using modular or fallback method"""
        if self.trace_creator:
            return self.trace_creator.create_all_traces(
                data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data,
                existing_mer_traces=existing_mer_traces, manual_mer_data=manual_mer_data,
                snr_threshold_lower=snr_threshold_lower, snr_threshold_upper=snr_threshold_upper
            )
        else:
            # Fallback to inline trace creation
            return self._create_traces_fallback(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data,
                                              existing_mer_traces=existing_mer_traces, manual_mer_data=manual_mer_data,
                                              snr_threshold_lower=snr_threshold_lower, snr_threshold_upper=snr_threshold_upper)
    
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
    
    def _extract_existing_mer_traces(self, current_figure):
        """Extract existing MER traces from current figure"""
        existing_mer_traces = []
        if current_figure and 'data' in current_figure:
            for trace in current_figure['data']:
                if (isinstance(trace, dict) and 
                    'name' in trace and 
                    trace['name'] and 
                    ('MER High-Res Data' in trace['name'] or 'MER Tiles High-Res Data' in trace['name'])):
                    # Convert dict to Scattergl object for consistency
                    existing_trace = go.Scattergl(
                        x=trace.get('x', []),
                        y=trace.get('y', []),
                        mode=trace.get('mode', 'markers'),
                        marker=trace.get('marker', {}),
                        name=trace.get('name', 'MER Data'),
                        text=trace.get('text', []),
                        hoverinfo=trace.get('hoverinfo', 'text'),
                        showlegend=trace.get('showlegend', True)
                    )
                    existing_mer_traces.append(existing_trace)
        return existing_mer_traces
    
    def _calculate_filtered_count(self, merged_data, snr_lower, snr_upper):
        """Calculate filtered cluster count based on SNR range"""
        if snr_lower is None and snr_upper is None:
            return len(merged_data)
        elif snr_lower is not None and snr_upper is not None:
            return len(merged_data[(merged_data['SNR_CLUSTER'] >= snr_lower) & 
                                 (merged_data['SNR_CLUSTER'] <= snr_upper)])
        elif snr_upper is not None and snr_lower is None:
            return len(merged_data[merged_data['SNR_CLUSTER'] <= snr_upper])
        elif snr_lower is not None:
            return len(merged_data[merged_data['SNR_CLUSTER'] >= snr_lower])
        else:
            return len(merged_data)
    
    def _create_status_info(self, algorithm, data, filtered_merged_count, snr_lower, snr_upper, 
                           show_polygons, show_mer_tiles, free_aspect_ratio, alert_color, is_update=False):
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
            snr_filter_text = f"SNR: {snr_lower} ≤ SNR ≤ {snr_upper}"
        elif snr_lower is not None:
            snr_filter_text = f"SNR ≥ {snr_lower}"
        elif snr_upper is not None:
            snr_filter_text = f"SNR ≤ {snr_upper}"
        
        timestamp_text = "Updated at" if is_update else "Rendered at"
        
        status = dbc.Alert([
            html.H6(f"Algorithm: {algorithm}", className="mb-1"),
            html.P(f"Merged clusters: {filtered_merged_count}/{len(data['merged_data'])} (filtered)", className="mb-1"),
            html.P(f"Individual tiles: {len(data['tile_data'])}", className="mb-1"),
            html.P(f"SNR Filter: {snr_filter_text}", className="mb-1"),
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
            'merged_data': pd.DataFrame(),
            'tile_data': pd.DataFrame(),
            'snr_min': 0,
            'snr_max': 100
        }
    
    def _create_traces_fallback(self, data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data,
                               existing_mer_traces=None, manual_mer_data=None, snr_threshold_lower=None, snr_threshold_upper=None):
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
