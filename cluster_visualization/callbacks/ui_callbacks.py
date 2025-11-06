"""
UI callbacks for cluster visualization
"""

import dash
from dash import Input, Output, html


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
        self._setup_catred_visibility_callback()
        self._setup_collapsible_callbacks()
    
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
            Output('catred-render-button', 'children'),
            [Input('catred-render-button', 'n_clicks')],
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
            Output('catred-clear-button', 'children'),
            [Input('catred-clear-button', 'n_clicks')],
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

        @self.app.callback(
            Output('matching-clusters-switch', 'disabled'),
            [Input('algorithm-dropdown', 'value')],
            prevent_initial_call=False
        )
        def toggle_matching_clusters_switch(algorithm):
            """Enable matching-clusters-switch only when algorithm is BOTH"""
            # Enable the switch only when algorithm is 'BOTH'
            is_disabled = algorithm != 'BOTH'
            print(f"🔄 Algorithm dropdown callback: algorithm={algorithm}, matching-switch-disabled={is_disabled}")
            return is_disabled

    def _setup_catred_visibility_callback(self):
        """Setup clientside callback to show/hide CATRED controls based on catred-mode-switch"""
        self.app.clientside_callback(
            """
            function(catredEnabled) {
                // Convert boolean to display style
                let displayStyle = catredEnabled ? 'block' : 'none';
                
                // Return the display style for all 3 container elements
                return [
                    {display: displayStyle},
                    {display: displayStyle}, 
                    {display: displayStyle}
                ];
            }
            """,
            [Output('catred-threshold-container', 'style'),
             Output('magnitude-limit-container', 'style')],
            #  Output('catred-controls-container', 'style')],
            [Input('catred-mode-switch', 'value')],
            prevent_initial_call=False
        )
    
    def _setup_collapsible_callbacks(self):
        """Setup callbacks for collapsible sections"""
        # Core Settings Section
        @self.app.callback(
            [Output('core-settings-collapse', 'is_open'),
             Output('core-settings-toggle', 'children')],
            [Input('core-settings-toggle', 'n_clicks')],
            prevent_initial_call=False
        )
        def toggle_core_settings(n_clicks):
            """Toggle core settings section"""
            if n_clicks is None:
                return False, [  # 🔧 Changed from True to False
                    html.I(className="fas fa-chevron-right me-2"),  # 🔧 Changed to right arrow
                    "🎯 Core Settings"
                ]
            
            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [
                html.I(className=f"{icon} me-2"),
                "🎯 Core Settings"
            ]
        
        # Display Options Section
        @self.app.callback(
            [Output('display-options-collapse', 'is_open'),
             Output('display-options-toggle', 'children')],
            [Input('display-options-toggle', 'n_clicks')],
            prevent_initial_call=False
        )
        def toggle_display_options(n_clicks):
            """Toggle display options section"""
            if n_clicks is None:
                return False, [  # 🔧 Changed from True to False to match layout
                    html.I(className="fas fa-chevron-right me-2"),  # 🔧 Changed to right arrow
                    "🎨 Display Options"
                ]
            
            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [
                html.I(className=f"{icon} me-2"),
                "🎨 Display Options"
            ]
        
        # Advanced Data Section
        @self.app.callback(
            [Output('advanced-data-collapse', 'is_open'),
             Output('advanced-data-toggle', 'children')],
            [Input('advanced-data-toggle', 'n_clicks')],
            prevent_initial_call=False
        )
        def toggle_advanced_data(n_clicks):
            """Toggle advanced data section"""
            if n_clicks is None:
                return False, [
                    html.I(className="fas fa-chevron-right me-2"),
                    "🔬 Advanced Data"
                ]
            
            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [
                html.I(className=f"{icon} me-2"),
                "🔬 Advanced Data"
            ]
        
        # Image Controls Section
        @self.app.callback(
            [Output('image-controls-collapse', 'is_open'),
             Output('image-controls-toggle', 'children')],
            [Input('image-controls-toggle', 'n_clicks')],
            prevent_initial_call=False
        )
        def toggle_image_controls(n_clicks):
            """Toggle image controls section"""
            if n_clicks is None:
                return False, [
                    html.I(className="fas fa-chevron-right me-2"),
                    "🖼️ Image Controls"
                ]
            
            is_open = (n_clicks % 2) == 1
            icon = "fas fa-chevron-up" if is_open else "fas fa-chevron-down"
            return is_open, [
                html.I(className=f"{icon} me-2"),
                "🖼️ Image Controls"
            ]
