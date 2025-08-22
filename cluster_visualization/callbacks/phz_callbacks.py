"""
PHZ (Photometric Redshift) callbacks for cluster visualization.

Handles PHZ_PDF plot updates when clicking on MER data points,
including redshift distribution visualization and mode highlighting.
"""

import dash
from dash import Input, Output
import plotly.graph_objs as go
import numpy as np


class PHZCallbacks:
    """Handles PHZ_PDF plot callbacks"""
    
    def __init__(self, app, catred_handler=None):
        """
        Initialize PHZ callbacks.
        
        Args:
            app: Dash application instance
            catred_handler: CATREDHandler instance for MER data operations (optional)
        """
        self.app = app
        self.catred_handler = catred_handler
        
        # Fallback attributes for backward compatibility
        self.current_catred_data = None
        
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """Setup all PHZ-related callbacks"""
        self._setup_phz_pdf_callback()
    
    def _setup_phz_pdf_callback(self):
        """Setup callback for handling clicks on MER data points to show PHZ_PDF"""
        @self.app.callback(
            Output('phz-pdf-plot', 'figure', allow_duplicate=True),
            [Input('cluster-plot', 'clickData')],
            prevent_initial_call=True
        )
        def update_phz_pdf_plot(clickData):
            print(f"Debug: Click callback triggered with clickData: {clickData}")
            
            if not clickData:
                print("Debug: No clickData received")
                return dash.no_update
            
            # Get current MER data from handler or fallback
            current_mer_data = None
            if self.catred_handler and hasattr(self.catred_handler, 'current_catred_data') and self.catred_handler.current_catred_data:
                current_mer_data = self.catred_handler.current_catred_data
                print("Debug: Using current_catred_data from catred_handler")
            elif hasattr(self, 'trace_creator') and self.trace_creator and hasattr(self.trace_creator, 'current_catred_data') and self.trace_creator.current_catred_data:
                current_mer_data = self.trace_creator.current_catred_data
                print("Debug: Using current_catred_data from trace_creator")
            elif hasattr(self, 'current_catred_data') and self.current_catred_data:
                current_mer_data = self.current_catred_data
                print("Debug: Using current_catred_data from self")
            
            if not current_mer_data:
                print(f"Debug: No current_catred_data available: {current_mer_data}")
                return dash.no_update
            
            try:
                # Extract click information
                clicked_point = clickData['points'][0]
                print(f"Debug: Clicked point: {clicked_point}")
                
                # Get coordinates for matching
                clicked_x = clicked_point.get('x')
                clicked_y = clicked_point.get('y')
                print(f"Debug: Clicked coordinates: ({clicked_x}, {clicked_y})")
                
                # Get custom data (point index) if available
                custom_data = clicked_point.get('customdata', None)
                print(f"Debug: Custom data: {custom_data}")
                
                # Search through stored MER data to find the matching trace
                found_mer_data = None
                point_index = None
                
                print(f"Debug: Available MER data traces: {list(current_mer_data.keys())}")
                
                for trace_name, mer_data in current_mer_data.items():
                    print(f"Debug: Checking trace: {trace_name}")
                    if 'MER High-Res Data' in trace_name:
                        print(f"Debug: Found MER trace with {len(mer_data['ra'])} points")
                        
                        # If we have custom data (point index), use it directly
                        if custom_data is not None and isinstance(custom_data, int) and custom_data < len(mer_data['ra']):
                            found_mer_data = mer_data
                            point_index = custom_data
                            print(f"Debug: Using custom data index: {point_index}")
                            break
                        
                        # Otherwise, find the point index by matching coordinates (less reliable but fallback)
                        if clicked_x is not None and clicked_y is not None:
                            for i, (x, y) in enumerate(zip(mer_data['ra'], mer_data['dec'])):
                                if abs(x - clicked_x) < 1e-6 and abs(y - clicked_y) < 1e-6:
                                    found_mer_data = mer_data
                                    point_index = i
                                    print(f"Debug: Found matching point by coordinates at index: {point_index}")
                                    break
                        
                        if found_mer_data:
                            break
                
                if found_mer_data and point_index is not None:
                    print(f"Debug: Successfully found MER data for point index: {point_index}")
                    
                    # Get PHZ_PDF data for this point
                    phz_pdf = found_mer_data['phz_pdf'][point_index]
                    ra = found_mer_data['ra'][point_index]
                    dec = found_mer_data['dec'][point_index]
                    phz_mode_1 = found_mer_data['phz_mode_1'][point_index]
                    
                    print(f"Debug: PHZ_PDF length: {len(phz_pdf)}, PHZ_MODE_1: {phz_mode_1}")
                    
                    return self._create_phz_pdf_plot(phz_pdf, ra, dec, phz_mode_1)
                else:
                    print("Debug: Click was not on a MER data point")
                
                # If we get here, the click wasn't on a MER point
                return dash.no_update
                
            except Exception as e:
                print(f"Debug: Error creating PHZ_PDF plot: {e}")
                import traceback
                print(f"Debug: Traceback: {traceback.format_exc()}")
                
                return self._create_error_phz_plot(str(e))
    
    def _create_phz_pdf_plot(self, phz_pdf, ra, dec, phz_mode_1):
        """Create PHZ_PDF plot for a given MER point"""
        try:
            # Validate PHZ_PDF data
            if not phz_pdf or len(phz_pdf) == 0:
                print(f"Debug: Empty PHZ_PDF data")
                return self._create_error_phz_plot("Empty PHZ_PDF data")
            
            # Convert to numpy array for safety
            phz_pdf_array = np.array(phz_pdf)
            
            # Check for NaN or infinite values
            if np.any(np.isnan(phz_pdf_array)) or np.any(np.isinf(phz_pdf_array)):
                print(f"Debug: PHZ_PDF contains NaN or infinite values")
                return self._create_error_phz_plot("PHZ_PDF contains invalid values")
            
            # Create redshift bins (assuming typical range for photometric redshift)
            z_bins = np.linspace(0, 3, len(phz_pdf_array))
            
            # Create PHZ_PDF plot
            phz_fig = go.Figure()
            
            phz_fig.add_trace(go.Scatter(
                x=z_bins,
                y=phz_pdf_array,
                mode='lines+markers',
                name='PHZ_PDF',
                line=dict(color='blue', width=2),
                marker=dict(size=4),
                fill='tozeroy'  # Fill to zero y-axis instead of previous trace
            ))
            
            # Add vertical line for PHZ_MODE_1
            phz_fig.add_vline(
                x=phz_mode_1,
                line=dict(color='red', width=2, dash='dash'),
                annotation_text=f"PHZ_MODE_1: {phz_mode_1:.3f}",
                annotation_position="top"
            )
            
            phz_fig.update_layout(
                title=f'PHZ_PDF for MER Point at RA: {ra:.6f}, Dec: {dec:.6f}',
                xaxis_title='Redshift (z)',
                yaxis_title='Probability Density',
                margin=dict(l=40, r=20, t=60, b=40),
                showlegend=True,
                hovermode='x unified'
            )
            
            print(f"Debug: Created PHZ_PDF plot for point at RA: {ra:.6f}, Dec: {dec:.6f}")
            return phz_fig
            
        except Exception as e:
            print(f"Debug: Error in _create_phz_pdf_plot: {e}")
            import traceback
            print(f"Debug: Traceback: {traceback.format_exc()}")
            return self._create_error_phz_plot(f"Error creating plot: {str(e)}")
    
    def _create_error_phz_plot(self, error_message):
        """Create error PHZ_PDF plot"""
        error_fig = go.Figure()
        error_fig.update_layout(
            title='PHZ_PDF Plot - Error',
            xaxis_title='Redshift',
            yaxis_title='Probability Density',
            margin=dict(l=40, r=20, t=40, b=40),
            showlegend=False,
            annotations=[
                dict(
                    text=f"Error loading PHZ_PDF data: {error_message}",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, xanchor='center', yanchor='middle',
                    showarrow=False,
                    font=dict(size=12, color="red")
                )
            ]
        )
        return error_fig
