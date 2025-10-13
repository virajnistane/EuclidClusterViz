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
        # Use a dummy interval to trigger initial callback and then button clicks
        @self.app.callback(
            Output('render-button', 'children'),
            [Input('render-button', 'n_clicks')],
            prevent_initial_call=False
        )
        def update_main_button_text(n_clicks):
            """Update main render button text"""
            if n_clicks is None:
                n_clicks = 0
            return "🚀 Initial Render" if n_clicks == 0 else f"✅ Live Updates Active ({n_clicks})"

        @self.app.callback(
            Output('mer-render-button', 'children'),
            [Input('mer-render-button', 'n_clicks')],
            prevent_initial_call=False
        )
        def update_catred_button_text(catred_n_clicks):
            """Update CATRED button text"""
            if catred_n_clicks is None:
                catred_n_clicks = 0
            return f"🔍 Render CATRED Data ({catred_n_clicks})" if catred_n_clicks > 0 else "🔍 Render CATRED Data"

        @self.app.callback(
            Output('snr-render-button', 'children'),
            [Input('snr-render-button', 'n_clicks')],
            prevent_initial_call=False
        )
        def update_snr_button_text(snr_n_clicks):
            """Update SNR button text"""
            if snr_n_clicks is None:
                snr_n_clicks = 0
            return f"🎯 Update SNR Filter ({snr_n_clicks})" if snr_n_clicks > 0 else "🎯 Update SNR Filter"

        @self.app.callback(
            Output('redshift-render-button', 'children'),
            [Input('redshift-render-button', 'n_clicks')],
            prevent_initial_call=False
        )
        def update_redshift_button_text(redshift_n_clicks):
            """Update redshift button text"""
            if redshift_n_clicks is None:
                redshift_n_clicks = 0
            return f"🌌 Update Redshift Filter ({redshift_n_clicks})" if redshift_n_clicks > 0 else "🌌 Update Redshift Filter"

        @self.app.callback(
            Output('mer-clear-button', 'children'),
            [Input('mer-clear-button', 'n_clicks')],
            prevent_initial_call=False
        )
        def update_clear_button_text(clear_n_clicks):
            """Update clear button text with click count"""
            clear_n_clicks = clear_n_clicks or 0
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
            """Enable SNR and redshift filter buttons after initial render"""
            # Disable both buttons until initial render is clicked
            n_clicks = n_clicks or 0
            disabled = n_clicks == 0
            return disabled, disabled

        @self.app.callback(
            Output('mosaic-render-button', 'disabled'),
            [Input('mosaic-enable-switch', 'value')],
            prevent_initial_call=False
        )
        def toggle_mosaic_button(mosaic_enabled):
            """Enable/disable mosaic render button based on switch state"""
            print(f"🔄 Mosaic switch callback: mosaic_enabled={mosaic_enabled}, button_disabled={not mosaic_enabled}")
            return not mosaic_enabled  # Button is enabled when switch is True
