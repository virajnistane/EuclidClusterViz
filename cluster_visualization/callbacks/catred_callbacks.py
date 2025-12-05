"""
CATRED (Reduced Catalog) callbacks for cluster visualization.

Handles CATRED data rendering, clearing, and related UI interactions.
Includes zoom-dependent CATRED button state management.
"""

import dash  # type: ignore[import]
from dash import Input, Output, State, html
import plotly.graph_objs as go # type: ignore[import]
import pandas as pd # type: ignore[import]
import dash_bootstrap_components as dbc # type: ignore[import]


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
        self._setup_catred_visibility_toggle_callback()
        self._setup_catred_control_buttons_state_callback()
    
    def _setup_catred_button_state_callback(self):
        """Setup callback to enable/disable CATRED render button based on zoom level"""
        @self.app.callback(
            Output('catred-render-button', 'disabled'),
            [Input('cluster-plot', 'relayoutData'),
             Input('mer-switch', 'value')],
            #  Input('catred-mode-switch', 'value')],
            [State('render-button', 'n_clicks')],
            prevent_initial_call=True
        )
        def update_mer_button_state(relayout_data, show_mer_tiles, n_clicks):
            # Only enable if main app has been rendered and conditions are met
            if n_clicks == 0:
                return True  # Disabled
            
            if not show_mer_tiles:
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
             State('matching-clusters-switch', 'value'),
             State('snr-range-slider-pzwav', 'value'),
             State('snr-range-slider-amico', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('merged-clusters-switch', 'value'),
             State('catred-mode-switch', 'value'),
             State('catred-threshold-slider', 'value'),
             State('magnitude-limit-slider', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def manual_render_catred_data(catred_n_clicks, 
                                      algorithm, matching_clusters, snr_range_pzwav, snr_range_amico, show_polygons, show_mer_tiles, free_aspect_ratio, 
                                      show_merged_clusters, catred_masked, threshold, maglim, relayout_data, current_figure):
            if catred_n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update
            
            print(f"Debug: Manual CATRED render button clicked (click #{catred_n_clicks}) with threshold={threshold}, maglim={maglim}")
            
            try:
                # Extract SNR values from range sliders (separate for PZWAV and AMICO)
                snr_pzwav_lower = snr_range_pzwav[0] if snr_range_pzwav and len(snr_range_pzwav) == 2 else None
                snr_pzwav_upper = snr_range_pzwav[1] if snr_range_pzwav and len(snr_range_pzwav) == 2 else None
                
                snr_amico_lower = snr_range_amico[0] if snr_range_amico and len(snr_range_amico) == 2 else None
                snr_amico_upper = snr_range_amico[1] if snr_range_amico and len(snr_range_amico) == 2 else None
                
                # Determine which SNR range to use based on algorithm
                if algorithm == 'PZWAV':
                    snr_lower = snr_pzwav_lower
                    snr_upper = snr_pzwav_upper
                elif algorithm == 'AMICO':
                    snr_lower = snr_amico_lower
                    snr_upper = snr_amico_upper
                else:  # BOTH
                    snr_lower = (snr_pzwav_lower, snr_amico_lower)
                    snr_upper = (snr_pzwav_upper, snr_amico_upper)
                
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Load CATRED scatter data for current zoom window with threshold
                catred_scatter_data = self.load_catred_scatter_data(data, relayout_data, catred_masked, threshold, maglim)
                
                # Extract existing CATRED traces from current figure to preserve them
                existing_catred_traces = self._extract_existing_catred_traces(current_figure)
                
                # 🆕 EXTRACT EXISTING MOSAIC TRACES TO PRESERVE THEM
                existing_mosaic_traces = self._extract_existing_mosaic_traces(current_figure)
                
                # 🆕 EXTRACT EXISTING MASK OVERLAY TRACES TO PRESERVE THEM
                existing_mask_overlay_traces = self._extract_existing_mask_overlay_traces(current_figure)

                print(f"Debug: Found {len(existing_catred_traces)} existing CATRED traces to preserve")
                print(f"Debug: Found {len(existing_mosaic_traces)} existing mosaic traces to preserve")
                print(f"Debug: Found {len(existing_mask_overlay_traces)} existing mask overlay traces to preserve")

                # Create traces with the manually loaded CATRED data and existing traces
                traces = self.create_traces(
                    data, show_polygons, show_mer_tiles, relayout_data, catred_masked,
                    manual_catred_data=catred_scatter_data,
                    existing_catred_traces=existing_catred_traces,
                    existing_mosaic_traces=existing_mosaic_traces,  # 🆕 PASS MOSAIC TRACES
                    existing_mask_overlay_traces=existing_mask_overlay_traces,  # 🆕 PASS MASK OVERLAY TRACES
                    snr_threshold_lower_pzwav=snr_pzwav_lower, snr_threshold_upper_pzwav=snr_pzwav_upper,
                    snr_threshold_lower_amico=snr_amico_lower, snr_threshold_upper_amico=snr_amico_upper,
                    threshold=threshold, show_merged_clusters=show_merged_clusters, matching_clusters=matching_clusters
                )

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
             State('matching-clusters-switch', 'value'),
             State('snr-range-slider-pzwav', 'value'),
             State('snr-range-slider-amico', 'value'),
             State('redshift-range-slider', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('merged-clusters-switch', 'value'),
             State('catred-mode-switch', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure'),
             State('render-button', 'n_clicks')],
            prevent_initial_call=True
        )
        def clear_catred_data(clear_n_clicks, algorithm, matching_clusters, snr_range_pzwav, snr_range_amico, redshift_range, show_polygons, show_mer_tiles, free_aspect_ratio, show_merged_clusters, catred_masked, relayout_data, current_figure, render_n_clicks):
            if clear_n_clicks == 0 or render_n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update
            
            print(f"Debug: Clear CATRED data button clicked (click #{clear_n_clicks})")
            
            try:
                # Extract SNR values from range sliders (separate for PZWAV and AMICO)
                snr_pzwav_lower = snr_range_pzwav[0] if snr_range_pzwav and len(snr_range_pzwav) == 2 else None
                snr_pzwav_upper = snr_range_pzwav[1] if snr_range_pzwav and len(snr_range_pzwav) == 2 else None
                
                snr_amico_lower = snr_range_amico[0] if snr_range_amico and len(snr_range_amico) == 2 else None
                snr_amico_upper = snr_range_amico[1] if snr_range_amico and len(snr_range_amico) == 2 else None
                
                # Determine which SNR range to use based on algorithm
                if algorithm == 'PZWAV':
                    snr_lower = snr_pzwav_lower
                    snr_upper = snr_pzwav_upper
                elif algorithm == 'AMICO':
                    snr_lower = snr_amico_lower
                    snr_upper = snr_amico_upper
                else:  # BOTH
                    snr_lower = (snr_pzwav_lower, snr_amico_lower)
                    snr_upper = (snr_pzwav_upper, snr_amico_upper)
                
                # Extract redshift values from range slider
                z_lower = redshift_range[0] if redshift_range and len(redshift_range) == 2 else None
                z_upper = redshift_range[1] if redshift_range and len(redshift_range) == 2 else None
                
                # Clear CATRED traces cache
                if self.catred_handler:
                    self.catred_handler.clear_traces_cache()
                else:
                    self.catred_traces_cache = []
                
                # 🆕 CLEAR CATRED DATA IN TRACE CREATOR TO REVERT MARKER ENHANCEMENTS
                if self.trace_creator:
                    self.trace_creator.clear_catred_data()
                    print("Debug: Cleared CATRED data in TraceCreator to revert marker enhancements")
                
                # 🆕 EXTRACT EXISTING MOSAIC TRACES TO PRESERVE THEM
                existing_mosaic_traces = self._extract_existing_mosaic_traces(current_figure)
                print(f"Debug: Clear CATRED - preserving {len(existing_mosaic_traces)} existing mosaic traces")

                existing_mask_overlay_traces = self._extract_existing_mask_overlay_traces(current_figure)
                print(f"Debug: Clear CATRED - preserving {len(existing_mask_overlay_traces)} existing mask overlay traces")

                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Create traces without any CATRED data, but preserve mosaic traces
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, catred_masked='none',
                                          existing_mosaic_traces=existing_mosaic_traces,  # 🆕 PRESERVE MOSAIC TRACES
                                          existing_mask_overlay_traces=existing_mask_overlay_traces,  # 🆕 PRESERVE MASK OVERLAY TRACES
                                          snr_threshold_lower_pzwav=snr_pzwav_lower, snr_threshold_upper_pzwav=snr_pzwav_upper,
                                          snr_threshold_lower_amico=snr_amico_lower, snr_threshold_upper_amico=snr_amico_upper,
                                          z_threshold_lower=z_lower, z_threshold_upper=z_upper,  # 🔧 ADD REDSHIFT PARAMS
                                          show_merged_clusters=show_merged_clusters, matching_clusters=matching_clusters)
                
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

    def load_catred_scatter_data(self, data, relayout_data, catred_masked=False, threshold=0.8, maglim=None):
        """Load CATRED scatter data using modular or fallback method"""
        if self.catred_handler:
            return self.catred_handler.load_catred_scatter_data(data, relayout_data, catred_masked, threshold, maglim)
        else:
            # Fallback to inline CATRED data loading
            return self._load_catred_scatter_data_fallback(data, relayout_data)
    
    def create_traces(self, data, show_polygons, show_mer_tiles, relayout_data, catred_masked, 
                     existing_catred_traces=None, existing_mosaic_traces=None, existing_mask_overlay_traces=None,
                     manual_catred_data=None, snr_threshold_lower_pzwav=None, snr_threshold_upper_pzwav=None, snr_threshold_lower_amico=None, snr_threshold_upper_amico=None, 
                     z_threshold_lower=None, z_threshold_upper=None, threshold=0.8, show_merged_clusters=True, matching_clusters=False):
        """Create traces using modular or fallback method"""
        if self.trace_creator:
            return self.trace_creator.create_traces(
                data, show_polygons, show_mer_tiles, relayout_data, catred_masked,
                existing_catred_traces=existing_catred_traces, existing_mosaic_traces=existing_mosaic_traces, existing_mask_overlay_traces=existing_mask_overlay_traces, manual_catred_data=manual_catred_data, 
                snr_threshold_lower_pzwav=snr_threshold_lower_pzwav, snr_threshold_upper_pzwav=snr_threshold_upper_pzwav, snr_threshold_lower_amico=snr_threshold_lower_amico, snr_threshold_upper_amico=snr_threshold_upper_amico, 
                z_threshold_lower=z_threshold_lower, z_threshold_upper=z_threshold_upper, threshold=threshold, show_merged_clusters=show_merged_clusters,
                matching_clusters=matching_clusters
            )
        else:
            # Fallback to inline trace creation
            return self._create_traces_fallback(data, show_polygons, show_mer_tiles, relayout_data, catred_masked,
                                              existing_catred_traces=existing_catred_traces, 
                                              existing_mosaic_traces=existing_mosaic_traces,  # 🆕 ADD MOSAIC TRACES
                                              existing_mask_overlay_traces=existing_mask_overlay_traces,
                                              manual_catred_data=manual_catred_data,
                                              snr_threshold_lower_pzwav=snr_threshold_lower_pzwav, snr_threshold_upper_pzwav=snr_threshold_upper_pzwav, 
                                              snr_threshold_lower_amico=snr_threshold_lower_amico, snr_threshold_upper_amico=snr_threshold_upper_amico, 
                                              z_threshold_lower=z_threshold_lower, z_threshold_upper=z_threshold_upper, threshold=threshold, 
                                              show_merged_clusters=show_merged_clusters, matching_clusters=matching_clusters)

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
    
    def _extract_existing_mosaic_traces(self, current_figure):
        """Extract existing mosaic traces from current figure"""
        existing_mosaic_traces = []
        if current_figure and 'data' in current_figure:
            for trace in current_figure['data']:
                if (isinstance(trace, dict) and 
                    'name' in trace and 
                    trace['name'] and 
                    'Mosaic' in trace['name']):
                    # Preserve the original trace type (Image, Heatmap, etc.)
                    trace_type = trace.get('type', 'image')
                    
                    if trace_type == 'image':
                        existing_trace = go.Image(
                            source=trace.get('source'),
                            x0=trace.get('x0'),
                            y0=trace.get('y0'),
                            dx=trace.get('dx'),
                            dy=trace.get('dy'),
                            name=trace.get('name', 'Mosaic Image'),
                            opacity=trace.get('opacity', 1.0),
                            layer=trace.get('layer', 'below')
                        )
                    elif trace_type == 'heatmap':
                        existing_trace = go.Heatmap(
                            z=trace.get('z'),
                            x=trace.get('x'),
                            y=trace.get('y'),
                            name=trace.get('name', 'Mosaic Image'),
                            opacity=trace.get('opacity', 1.0),
                            colorscale=trace.get('colorscale', 'gray'),
                            showscale=trace.get('showscale', False)
                        )
                    else:
                        # Keep original trace as-is for unknown types
                        existing_trace = trace
                    
                    existing_mosaic_traces.append(existing_trace)
                    print(f"Debug: Preserved existing mosaic trace: {trace['name']} (type: {trace_type})")
        return existing_mosaic_traces

    def _extract_existing_mask_overlay_traces(self, current_figure):
        """Extract existing mask overlay traces from current figure"""
        existing_mask_overlay_traces = []
        if current_figure and 'data' in current_figure:
            for trace in current_figure['data']:
                if (isinstance(trace, dict) and 
                    'name' in trace and 
                    trace['name'] and 
                    'Mask overlay' in trace['name']):
                    # Preserve the original trace type (Image, Heatmap, etc.)
                    trace_type = trace.get('type', 'image')
                    
                    if trace_type == 'image':
                        existing_trace = go.Image(
                            source=trace.get('source'),
                            x0=trace.get('x0'),
                            y0=trace.get('y0'),
                            dx=trace.get('dx'),
                            dy=trace.get('dy'),
                            name=trace.get('name', 'Mosaic Image'),
                            opacity=trace.get('opacity', 1.0),
                            layer=trace.get('layer', 'below')
                        )
                    elif trace_type == 'heatmap':
                        existing_trace = go.Heatmap(
                            z=trace.get('z'),
                            x=trace.get('x'),
                            y=trace.get('y'),
                            name=trace.get('name', 'Mosaic Image'),
                            opacity=trace.get('opacity', 1.0),
                            colorscale=trace.get('colorscale', 'gray'),
                            showscale=trace.get('showscale', False)
                        )
                    else:
                        # Keep original trace as-is for unknown types
                        existing_trace = trace

                    existing_mask_overlay_traces.append(existing_trace)
                    print(f"Debug: Preserved existing mask overlay trace: {trace['name']} (type: {trace_type})")
        return existing_mask_overlay_traces

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
    
    def _create_traces_fallback(self, data, show_polygons, show_mer_tiles, relayout_data, catred_masked,
                               existing_catred_traces=None, existing_mosaic_traces=None, existing_mask_overlay_traces=None,
                               manual_catred_data=None, snr_threshold_lower_pzwav=None, snr_threshold_upper_pzwav=None, 
                               snr_threshold_lower_amico=None, snr_threshold_upper_amico=None, 
                               z_threshold_lower=None, z_threshold_upper=None, threshold=0.8, show_merged_clusters=True):
        """Fallback trace creation method"""
        # This would contain the original inline trace creation logic
        # For now, return empty traces to prevent errors
        return []
    
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

    def _setup_catred_visibility_toggle_callback(self):
        """Setup clientside callback to toggle CATRED trace visibility without deleting from memory"""
        self.app.clientside_callback(
            """
            function(n_clicks, figure) {
                if (!n_clicks || !figure || !figure.data) {
                    return [figure, window.dash_clientside.no_update];
                }
                
                let newFigure = JSON.parse(JSON.stringify(figure));
                let hasCatredTraces = false;
                let allCatredHidden = true;
                
                // First pass: check if there are CATRED traces and their visibility state
                for (let i = 0; i < newFigure.data.length; i++) {
                    let trace = newFigure.data[i];
                    if (trace.name && (trace.name.includes('CATRED') || trace.name.includes('MER High-Res Data'))) {
                        hasCatredTraces = true;
                        if (trace.visible !== false && trace.visible !== 'legendonly') {
                            allCatredHidden = false;
                        }
                    }
                }
                
                if (!hasCatredTraces) {
                    return [figure, window.dash_clientside.no_update];
                }
                
                // Toggle visibility: if all hidden, show them; otherwise hide them
                let newVisibility = allCatredHidden ? true : 'legendonly';
                
                for (let i = 0; i < newFigure.data.length; i++) {
                    let trace = newFigure.data[i];
                    if (trace.name && (trace.name.includes('CATRED') || trace.name.includes('MER High-Res Data'))) {
                        newFigure.data[i].visible = newVisibility;
                    }
                }
                
                // Update button text and icon
                let buttonContent = allCatredHidden ? 
                    [{"namespace": "dash_html_components", "type": "I", "props": {"className": "fas fa-eye me-1"}}, "Hide"] :
                    [{"namespace": "dash_html_components", "type": "I", "props": {"className": "fas fa-eye-slash me-1"}}, "Show"];
                
                return [newFigure, buttonContent];
            }
            """,
            [Output('cluster-plot', 'figure', allow_duplicate=True),
             Output('catred-toggle-visibility-button', 'children')],
            [Input('catred-toggle-visibility-button', 'n_clicks')],
            [State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )

    def _setup_catred_control_buttons_state_callback(self):
        """Setup callback to enable/disable CATRED control buttons based on presence of CATRED traces"""
        self.app.clientside_callback(
            """
            function(figure) {
                if (!figure || !figure.data) {
                    return [true, true];  // Both disabled
                }
                
                // Check if there are any CATRED traces
                let hasCatredTraces = false;
                for (let i = 0; i < figure.data.length; i++) {
                    if (figure.data[i].name && (figure.data[i].name.includes('CATRED') || figure.data[i].name.includes('MER High-Res Data'))) {
                        hasCatredTraces = true;
                        break;
                    }
                }
                
                // Enable buttons if CATRED traces exist
                return [!hasCatredTraces, !hasCatredTraces];
            }
            """,
            [Output('catred-toggle-visibility-button', 'disabled'),
             Output('catred-clear-button', 'disabled')],
            [Input('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
    
    # Fallback methods for backward compatibility
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
