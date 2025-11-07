"""
MER-Mosaic and Mask overlay callbacks for cluster visualization.

Handles MER-Mosaic data rendering, clearing, and related UI interactions.
Includes zoom-dependent MER-Mosaic and mask button state management.
"""

import dash
from dash import Input, Output, State, html
import plotly.graph_objs as go
import pandas as pd
import dash_bootstrap_components as dbc


class MOSAICCallbacks:
    """Handles MER-Mosaic data-related callbacks"""

    def __init__(self, app, data_loader, mosaic_handler, trace_creator, figure_manager):
        """
        Initialize MER-Mosaic callbacks.
        
        Args:
            app: Dash application instance
            data_loader: DataLoader instance for data operations
            mosaic_handler: MosaicHandler instance for mosaic operations
            trace_creator: TraceCreator instance for trace creation
            figure_manager: FigureManager instance for figure layout
        """
        self.app = app
        self.data_loader = data_loader
        self.mosaic_handler = mosaic_handler
        self.trace_creator = trace_creator
        self.figure_manager = figure_manager
        
        # Fallback attributes for backward compatibility
        self.data_cache = {}
        
        self.setup_callbacks()

    def setup_callbacks(self):
        """Setup all MER-Mosaic- and Mask-related callbacks"""
        self._setup_mosaic_button_state_callback()
        self._setup_healpix_mask_button_state_callback()
        self._setup_mosaic_render_callback()
        self._setup_mask_overlay_callback()

    def _setup_mosaic_button_state_callback(self):
        """Setup callback to enable/disable MOSAIC render button based on zoom level"""
        @self.app.callback(
            Output('mosaic-render-button', 'disabled'),
            [Input('cluster-plot', 'relayoutData'),
             Input('mosaic-enable-switch', 'value')],
            [State('render-button', 'n_clicks')],
            prevent_initial_call=True
        )
        def update_mosaic_button_state(relayout_data, mosaic_enabled, n_clicks):
            # Only enable if main app has been rendered and conditions are met
            if n_clicks == 0:
                return True  # Disabled

            if not mosaic_enabled:
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

    def _setup_healpix_mask_button_state_callback(self):
        """Setup callback to enable/disable HEALPix mask button based on zoom level"""
        @self.app.callback(
            Output('healpix-mask-button', 'disabled'),
            [Input('cluster-plot', 'relayoutData')],
            [State('render-button', 'n_clicks')],
            prevent_initial_call=True
        )
        def update_healpix_mask_button_state(relayout_data, n_clicks):
            # Only enable if main app has been rendered and conditions are met
            if n_clicks == 0:
                return True  # Disabled

            if not relayout_data:
                return True  # Disabled - no zoom data
            
            # Check zoom level
            ra_range, dec_range = self._extract_zoom_ranges(relayout_data)
            
            # Enable button if zoomed in enough
            if ra_range is not None and dec_range is not None and ra_range < 2.0 and dec_range < 2.0:
                return False  # Enabled
            else:
                return True   # Disabled - not zoomed in enough
    
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
                                mask_overlay_traces = []
                                catred_traces = []
                                cluster_traces = []
                                other_traces = []
                                
                                for trace in existing_traces:
                                    trace_name = trace.get('name', '')
                                    if 'Tile' in trace_name and ('CORE' in trace_name or 'LEV1' in trace_name or 'MerTile' in trace_name):
                                        polygon_traces.append(trace)
                                    elif 'Mask overlay' in trace_name:
                                        mask_overlay_traces.append(trace)
                                    elif 'CATRED' in trace_name or 'MER High-Res Data' in trace_name:
                                        catred_traces.append(trace)
                                    elif any(keyword in trace_name for keyword in ['Merged Data', 'Tile', 'clusters']):
                                        cluster_traces.append(trace)
                                    else:
                                        other_traces.append(trace)
                                
                                # Layer order: polygons (bottom) → mosaic → CATRED → other → cluster traces (top)
                                new_data = polygon_traces + mosaic_traces + mask_overlay_traces + catred_traces + other_traces + cluster_traces
                                current_figure['data'] = new_data
                                
                                print(f"✓ Added {len(mosaic_traces)} mosaic image traces as 2nd layer from bottom")
                                print(f"   -> Layer order: {len(polygon_traces)} polygons, {len(mosaic_traces)} mosaics, "
                                      f"{len(mask_overlay_traces)} mask overlays, {len(catred_traces)} CATRED, "
                                      f"{len(other_traces)} other, {len(cluster_traces)} clusters (top)")
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

    def _setup_mask_overlay_callback(self):
        """Setup mask overlay toggle callback"""
        print(f"🔧 Setting up mask overlay callback, mosaic_handler: {self.mosaic_handler}")
        if not self.mosaic_handler:
            print("⚠️  Skipping mask overlay callback - no mosaic handler available")
            return  # Skip if no mosaic handler available

        print("✅ Adding mask overlay callback")

        @self.app.callback(
            Output('cluster-plot', 'figure', allow_duplicate=True),
            [Input('healpix-mask-button', 'n_clicks')],
            [State('cluster-plot', 'figure'),
             State('cluster-plot', 'relayoutData'),
             State('mosaic-enable-switch', 'value'),
             State('algorithm-dropdown', 'value')],
            prevent_initial_call=True
        )
        def render_mask_overlay(n_clicks, current_figure, relayout_data, mosaic_enabled, algorithm):
            """Render mosaic images when button is clicked"""
            try:
                print(f"🔍 Mask overlay callback triggered! n_clicks={n_clicks}")
                print(f"   -> relayout_data keys: {list(relayout_data.keys()) if relayout_data else None}")
                print(f"   -> algorithm: {algorithm}")
                print(f"   -> current_figure exists: {current_figure is not None}")

                if not n_clicks:
                    print(f"   -> Returning early: n_clicks is {n_clicks}")
                    return current_figure
                    
                print("🚀 Proceeding with Healpix (effective coverage) mask loading...")
                try:
                    print(f"   -> Loading data for algorithm: {algorithm}")
                    # Load current data
                    data = self.data_loader.load_data(algorithm)
                    print(f"   -> Data loaded successfully")
                    
                    # Get mosaic traces for current zoom window
                    if self.mosaic_handler:
                        mask_footprint_traces = self.mosaic_handler.load_mask_overlay_traces_in_zoom(
                            data, 
                            relayout_data, 
                            opacity=0.4, 
                            colorscale='viridis'
                            )
                        print(f"   -> Mask footprint traces result: {len(mask_footprint_traces) if mask_footprint_traces else 0} traces")

                        if mask_footprint_traces and len(mask_footprint_traces) > 0:
                            # Add mosaic traces to current figure with proper layering
                            if current_figure and 'data' in current_figure:
                                # Remove only existing mask overlay traces (keep mosaic traces)
                                existing_traces = [trace for trace in current_figure['data'] 
                                                 if not (trace.get('name', '').startswith('Mask overlay'))]
                                
                                # Separate traces by type to maintain proper layering order
                                polygon_traces = []
                                catred_traces = []
                                cluster_traces = []
                                mosaic_cutout_traces = []
                                mosaic_traces = []
                                other_traces = []
                                
                                for trace in existing_traces:
                                    trace_name = trace.get('name', '')
                                    if 'Tile' in trace_name and ('CORE' in trace_name or 'LEV1' in trace_name or 'MerTile' in trace_name):
                                        polygon_traces.append(trace)
                                    elif 'MER-Mosaic cutout' in trace_name:
                                        mosaic_cutout_traces.append(trace)
                                    elif trace_name.startswith('Mosaic'):
                                        mosaic_traces.append(trace)
                                    elif 'CATRED' in trace_name:
                                        catred_traces.append(trace)
                                    elif any(keyword in trace_name for keyword in ['Merged Data', 'Tile', 'clusters']):
                                        cluster_traces.append(trace)
                                    else:
                                        other_traces.append(trace)
                                
                                # Layer order: polygons (bottom) → mosaic → CATRED → other → cluster traces (top)
                                new_data = (polygon_traces 
                                            + mosaic_traces + mosaic_cutout_traces 
                                            + mask_footprint_traces 
                                            + catred_traces 
                                            + other_traces 
                                            + cluster_traces)
                                current_figure['data'] = new_data
                                
                                print(f"✓ Added {len(mask_footprint_traces)} mosaic image traces as 2nd layer from bottom")
                                print(f"   -> Layer order: {len(polygon_traces)} polygons, "
                                      f"{len(mosaic_traces)} mosaics, {len(mosaic_cutout_traces)} mosaic cutouts, "
                                      f"{len(mask_footprint_traces)} mask overlays, {len(catred_traces)} CATRED, "
                                      f"{len(other_traces)} other, {len(cluster_traces)} clusters (top)")
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