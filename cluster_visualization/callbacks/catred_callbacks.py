"""
CATRED (Reduced Catalog) callbacks for cluster visualization.

Handles CATRED data rendering, clearing, and related UI interactions.
Includes zoom-dependent CATRED button state management.
"""

import dash
from dash import Input, Output, State, html
import plotly.graph_objs as go
import pandas as pd
import dash_bootstrap_components as dbc


class CATREDCallbacks:
    """Handles CATRED data-related callbacks"""
    
    def __init__(self, app, data_loader, catred_handler, trace_creator, figure_manager):
        """
        Initialize CATRED callbacks.
        
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
        self.catred_traces_cache = []
        
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """Setup all CATRED-related callbacks"""
        self._setup_catred_button_state_callback()
        self._setup_manual_catred_render_callback()
        self._setup_clear_catred_callback()
    
    def _setup_catred_button_state_callback(self):
        """Setup callback to enable/disable CATRED render button based on zoom level"""
        @self.app.callback(
            Output('catred-render-button', 'disabled'),
            [Input('cluster-plot', 'relayoutData'),
             Input('mer-switch', 'value'),
             Input('catred-mode-switch', 'value')],
            [State('render-button', 'n_clicks')],
            prevent_initial_call=True
        )
        def update_mer_button_state(relayout_data, show_mer_tiles, catred_mode, n_clicks):
            # Only enable if main app has been rendered and conditions are met
            if n_clicks == 0:
                return True  # Disabled
            
            if not show_mer_tiles or catred_mode == "none":
                return True  # Disabled - switches not turned on
            
            if not relayout_data:
                return True  # Disabled - no zoom data
            
            # Check zoom level
            ra_range, dec_range = self._extract_zoom_ranges(relayout_data)
            
            # Enable button if zoomed in enough
            if ra_range is not None and dec_range is not None and ra_range < 2.0 and dec_range < 2.0:
                return False  # Enabled
            else:
                return True   # Disabled - not zoomed in enough
    
    def _setup_manual_catred_render_callback(self):
        """Setup callback for manual CATRED data rendering"""
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), 
             Output('phz-pdf-plot', 'figure', allow_duplicate=True), 
             Output('status-info', 'children', allow_duplicate=True)],
            [Input('catred-render-button', 'n_clicks')],
            [State('algorithm-dropdown', 'value'),
             State('snr-range-slider', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mode-switch', 'value'),
             State('catred-threshold-slider', 'value'),
             State('magnitude-limit-slider', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def manual_render_catred_data(catred_n_clicks, algorithm, snr_range, show_polygons, show_mer_tiles, free_aspect_ratio, catred_mode, threshold, maglim, relayout_data, current_figure):
            if catred_n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update
            
            print(f"Debug: Manual CATRED render button clicked (click #{catred_n_clicks}) with threshold={threshold}, maglim={maglim}")
            
            try:
                # Extract SNR values from range slider
                snr_lower = snr_range[0] if snr_range and len(snr_range) == 2 else None
                snr_upper = snr_range[1] if snr_range and len(snr_range) == 2 else None
                
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Load CATRED scatter data for current zoom window with threshold
                catred_scatter_data = self.load_catred_scatter_data(data, relayout_data, catred_mode, threshold, maglim)
                
                # Extract existing CATRED traces from current figure to preserve them
                existing_catred_traces = self._extract_existing_catred_traces(current_figure)
                
                print(f"Debug: Found {len(existing_catred_traces)} existing CATRED traces to preserve")
                
                # Create traces with the manually loaded CATRED data and existing traces
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, catred_mode, 
                                          manual_catred_data=catred_scatter_data, existing_catred_traces=existing_catred_traces,
                                          snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper, threshold=threshold)
                
                # Update the CATRED traces cache with the new trace count
                if catred_scatter_data and catred_scatter_data['ra']:
                    self.catred_traces_cache.extend(existing_catred_traces)
                    # Add the new trace placeholder (actual trace is created in create_traces)
                    self.catred_traces_cache.append(None)  # Placeholder for the new trace
                
                # Create figure
                fig = self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio) if self.figure_manager else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                
                # Preserve zoom state
                if self.figure_manager:
                    self.figure_manager.preserve_zoom_state(fig, relayout_data)
                else:
                    self._preserve_zoom_state_fallback(fig, relayout_data)
                
                # Status info
                total_catred_traces = len(existing_catred_traces) + (1 if catred_scatter_data and catred_scatter_data['ra'] else 0)
                catred_points_count = len(catred_scatter_data['ra']) if catred_scatter_data and catred_scatter_data['ra'] else 0
                catred_status = f" | CATRED high-res data: {catred_points_count} points in {total_catred_traces} regions"
                aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"
                
                status = dbc.Alert([
                    html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                    html.P(f"Merged clusters: {len(data['data_detcluster_mergedcat'])}", className="mb-1"),
                    html.P(f"Individual tiles: {len(data['data_detcluster_by_cltile'])}", className="mb-1"),
                    html.P(f"Polygon mode: {'Filled' if show_polygons else 'Outline'}{catred_status}", className="mb-1"),
                    html.P(f"Aspect ratio: {aspect_mode}", className="mb-1"),
                    html.Small(f"CATRED data rendered at: {pd.Timestamp.now().strftime('%H:%M:%S')}", className="text-muted")
                ], color="success", className="mt-2")
                
                # Create empty PHZ_PDF plot for CATRED render
                empty_phz_fig = self._create_empty_phz_plot()
                
                return fig, empty_phz_fig, status
                
            except Exception as e:
                error_status = dbc.Alert(f"Error rendering CATRED data: {str(e)}", color="danger")
                return dash.no_update, dash.no_update, error_status
    
    def _setup_clear_catred_callback(self):
        """Setup callback for clearing all CATRED data"""
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), 
             Output('phz-pdf-plot', 'figure', allow_duplicate=True), 
             Output('status-info', 'children', allow_duplicate=True)],
            [Input('catred-clear-button', 'n_clicks')],
            [State('algorithm-dropdown', 'value'),
             State('snr-lower-input', 'value'),
             State('snr-upper-input', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mertile-switch', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('render-button', 'n_clicks')],
            prevent_initial_call=True
        )
        def clear_catred_data(clear_n_clicks, algorithm, snr_lower, snr_upper, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, relayout_data, render_n_clicks):
            if clear_n_clicks == 0 or render_n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update
            
            print(f"Debug: Clear CATRED data button clicked (click #{clear_n_clicks})")
            
            try:
                # Clear CATRED traces cache
                if self.catred_handler:
                    self.catred_handler.clear_traces_cache()
                else:
                    self.catred_traces_cache = []
                
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Create traces without any CATRED data
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data,
                                          snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper)
                
                # Create figure
                fig = self.figure_manager.create_figure(traces, algorithm, free_aspect_ratio) if self.figure_manager else self._create_fallback_figure(traces, algorithm, free_aspect_ratio)
                
                # Preserve zoom state
                if self.figure_manager:
                    self.figure_manager.preserve_zoom_state(fig, relayout_data)
                else:
                    self._preserve_zoom_state_fallback(fig, relayout_data)
                
                # Status info
                catred_status = " | CATRED high-res data: cleared"
                aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"
                
                status = dbc.Alert([
                    html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                    html.P(f"Merged clusters: {len(data['data_detcluster_mergedcat'])}", className="mb-1"),
                    html.P(f"Individual tiles: {len(data['data_detcluster_by_cltile'])}", className="mb-1"),
                    html.P(f"Polygon mode: {'Filled' if show_polygons else 'Outline'}{catred_status}", className="mb-1"),
                    html.P(f"Aspect ratio: {aspect_mode}", className="mb-1"),
                    html.Small(f"CATRED data cleared at: {pd.Timestamp.now().strftime('%H:%M:%S')}", className="text-muted")
                ], color="warning", className="mt-2")
                
                # Create empty PHZ_PDF plot for clear action
                empty_phz_fig = self._create_empty_phz_plot("CATRED data cleared - Click on a CATRED data point to view its PHZ_PDF")
                
                return fig, empty_phz_fig, status
                
            except Exception as e:
                error_status = dbc.Alert(f"Error clearing CATRED data: {str(e)}", color="danger")
                return dash.no_update, dash.no_update, error_status
    
    def load_data(self, algorithm):
        """Load data using modular or fallback method"""
        if self.data_loader:
            return self.data_loader.load_data(algorithm)
        else:
            # Fallback to inline data loading
            return self._load_data_fallback(algorithm)
    
    def load_catred_scatter_data(self, data, relayout_data, catred_mode="unmasked", threshold=0.8, maglim=None):
        """Load CATRED scatter data using modular or fallback method"""
        if self.catred_handler:
            return self.catred_handler.load_catred_scatter_data(data, relayout_data, catred_mode, threshold, maglim)
        else:
            # Fallback to inline CATRED data loading
            return self._load_catred_scatter_data_fallback(data, relayout_data)
    
    def create_traces(self, data, show_polygons, show_mer_tiles, relayout_data, catred_mode, 
                     existing_catred_traces=None, manual_catred_data=None, snr_threshold_lower=None, snr_threshold_upper=None, threshold=0.8):
        """Create traces using modular or fallback method"""
        if self.trace_creator:
            return self.trace_creator.create_traces(
                data, show_polygons, show_mer_tiles, relayout_data, catred_mode,
                existing_catred_traces=existing_catred_traces, manual_catred_data=manual_catred_data,
                snr_threshold_lower=snr_threshold_lower, snr_threshold_upper=snr_threshold_upper, threshold=threshold
            )
        else:
            # Fallback to inline trace creation
            return self._create_traces_fallback(data, show_polygons, show_mer_tiles, relayout_data, catred_mode,
                                              existing_catred_traces=existing_catred_traces, manual_catred_data=manual_catred_data,
                                              snr_threshold_lower=snr_threshold_lower, snr_threshold_upper=snr_threshold_upper, threshold=threshold)
    
    # Helper methods
    def _extract_zoom_ranges(self, relayout_data):
        """Extract RA and Dec ranges from relayout data"""
        ra_range = None
        dec_range = None
        
        if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
            ra_range = abs(relayout_data['xaxis.range[1]'] - relayout_data['xaxis.range[0]'])
        elif 'xaxis.range' in relayout_data:
            ra_range = abs(relayout_data['xaxis.range'][1] - relayout_data['xaxis.range'][0])
            
        if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
            dec_range = abs(relayout_data['yaxis.range[1]'] - relayout_data['yaxis.range[0]'])
        elif 'yaxis.range' in relayout_data:
            dec_range = abs(relayout_data['yaxis.range'][1] - relayout_data['yaxis.range'][0])
        
        return ra_range, dec_range
    
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
                    print(f"Debug: Preserved existing CATRED trace: {trace['name']}")
        return existing_catred_traces
    
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
    
    # Fallback methods for backward compatibility
    def _load_data_fallback(self, algorithm):
        """Fallback data loading method"""
        # This would contain the original inline data loading logic
        # For now, return empty structure to prevent errors
        return {
            'data_detcluster_mergedcat': pd.DataFrame(),
            'data_detcluster_by_cltile': pd.DataFrame(),
            'snr_min': 0,
            'snr_max': 100
        }
    
    def _load_catred_scatter_data_fallback(self, data, relayout_data):
        """Fallback CATRED scatter data loading method"""
        # This would contain the original inline CATRED data loading logic
        # For now, return empty structure to prevent errors
        return {'ra': [], 'dec': [], 'phz_pdf': [], 'phz_mode_1': []}
    
    def _create_traces_fallback(self, data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data,
                               existing_catred_traces=None, manual_catred_data=None, snr_threshold_lower=None, snr_threshold_upper=None):
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
    
    def _preserve_zoom_state_fallback(self, fig, relayout_data):
        """Fallback zoom state preservation method"""
        if relayout_data:
            if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                fig.update_xaxes(range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']])
            elif 'xaxis.range' in relayout_data:
                fig.update_xaxes(range=relayout_data['xaxis.range'])
                
            if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                fig.update_yaxes(range=[relayout_data['yaxis.range[0]'], relayout_data['yaxis.range[1]']])
            elif 'yaxis.range' in relayout_data:
                fig.update_yaxes(range=relayout_data['yaxis.range'])
