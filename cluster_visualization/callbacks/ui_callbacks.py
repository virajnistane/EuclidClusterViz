"""
UI callbacks for cluster visualization
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
             Output('snr-render-button', 'children'),
             Output('redshift-render-button', 'children')],
            [Input('algorithm-dropdown', 'value'),
             Input('snr-range-slider', 'value'),
             Input('redshift-range-slider', 'value'),
             Input('polygon-switch', 'value'),
             Input('mer-switch', 'value'),
             Input('aspect-ratio-switch', 'value'),
             Input('catred-mertile-switch', 'value'),
             Input('render-button', 'n_clicks'),
             Input('mer-render-button', 'n_clicks'),
             Input('snr-render-button', 'n_clicks'),
             Input('redshift-render-button', 'n_clicks')]
        )
        def update_button_texts(algorithm, snr_range, redshift_range, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, n_clicks, catred_n_clicks, snr_n_clicks, redshift_n_clicks):
            main_button_text = "🚀 Initial Render" if n_clicks == 0 else "✅ Live Updates Active"
            catred_button_text = f"🔍 Render CATRED Data ({catred_n_clicks})" if catred_n_clicks > 0 else "🔍 Render CATRED Data"
            snr_button_text = f"🎯 Update SNR Filter ({snr_n_clicks})" if snr_n_clicks > 0 else "🎯 Update SNR Filter"
            redshift_button_text = f"🌌 Update Redshift Filter ({redshift_n_clicks})" if redshift_n_clicks > 0 else "🌌 Update Redshift Filter"
            return main_button_text, catred_button_text, snr_button_text, redshift_button_text

        @self.app.callback(
            Output('mer-clear-button', 'children'),
            [Input('mer-clear-button', 'n_clicks')]
        )
        def update_clear_button_text(clear_n_clicks):
            return f"🗑️ Clear All CATRED ({clear_n_clicks})" if clear_n_clicks > 0 else "🗑️ Clear All CATRED"
    
    def _setup_button_state_callbacks(self):
        """Setup callbacks to enable/disable buttons based on conditions"""
        @self.app.callback(
            [Output('snr-render-button', 'disabled'),
             Output('redshift-render-button', 'disabled')],
            [Input('render-button', 'n_clicks')],
            prevent_initial_call=False
        )
        def enable_snr_and_redshift_buttons(n_clicks):
            # Disable both buttons until initial render is clicked
            disabled = n_clicks == 0
            return disabled, disabled
        def enable_redshift_button(n_clicks):
            # Disable Redshift button until initial render is clicked
            return n_clicks == 0
