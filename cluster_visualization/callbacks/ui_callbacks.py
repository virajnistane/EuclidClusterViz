"""
UI callbacks for cluster visualization.

Handles user interface interactions including button text updates,
button state management, and other UI-related callbacks.
"""

import dash
from dash import Input, Output


class UICallbacks:
    """Handles UI-related callbacks"""
    
    def __init__(self, app):
        """
        Initialize UI callbacks.
        
        Args:
            app: Dash application instance
        """
        self.app = app
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """Setup all UI-related callbacks"""
        self._setup_button_text_callbacks()
        self._setup_button_state_callbacks()
    
    def _setup_button_text_callbacks(self):
        """Setup callbacks to update button text based on current settings"""
        @self.app.callback(
            [Output('render-button', 'children'), 
             Output('mer-render-button', 'children'), 
             Output('snr-render-button', 'children')],
            [Input('algorithm-dropdown', 'value'),
             Input('snr-range-slider', 'value'),
             Input('polygon-switch', 'value'),
             Input('mer-switch', 'value'),
             Input('aspect-ratio-switch', 'value'),
             Input('catred-mertile-switch', 'value'),
             Input('render-button', 'n_clicks'),
             Input('mer-render-button', 'n_clicks'),
             Input('snr-render-button', 'n_clicks')]
        )
        def update_button_texts(algorithm, snr_range, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, n_clicks, mer_n_clicks, snr_n_clicks):
            main_button_text = "🚀 Initial Render" if n_clicks == 0 else "✅ Live Updates Active"
            mer_button_text = f"🔍 Render MER Data ({mer_n_clicks})" if mer_n_clicks > 0 else "🔍 Render MER Data"
            snr_button_text = f"Apply SNR Filter ({snr_n_clicks})" if snr_n_clicks > 0 else "Apply SNR Filter"
            return main_button_text, mer_button_text, snr_button_text
        
        @self.app.callback(
            Output('mer-clear-button', 'children'),
            [Input('mer-clear-button', 'n_clicks')]
        )
        def update_clear_button_text(clear_n_clicks):
            return f"🗑️ Clear All MER ({clear_n_clicks})" if clear_n_clicks > 0 else "🗑️ Clear All MER"
    
    def _setup_button_state_callbacks(self):
        """Setup callbacks to enable/disable buttons based on conditions"""
        @self.app.callback(
            Output('snr-render-button', 'disabled'),
            [Input('render-button', 'n_clicks')],
            prevent_initial_call=False
        )
        def enable_snr_button(n_clicks):
            # Disable SNR button until initial render is clicked
            return n_clicks == 0
