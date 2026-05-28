"""
Aladin Lite overlay callbacks.

Overlay data (clusters + CATRED) is now built entirely clientside from the
Plotly figure traces — zero server round-trip.  This module retains only the
catred-ready re-trigger: when a background CATRED render completes it writes
to aladin-overlay-data-store so the JS bridge refreshes the CATRED catalog.
"""

from dash import Input, Output, State, no_update


class AladinCallbacks:
    """Triggers Aladin overlay refresh after background CATRED render completes."""

    def __init__(self, app, data_loader, catred_handler):
        self.app = app
        self.data_loader = data_loader
        self.catred_handler = catred_handler
        self.setup_callbacks()

    def setup_callbacks(self):
        self._setup_catred_ready_trigger()

    def _setup_catred_ready_trigger(self):
        """When background CATRED render finishes, nudge aladin-overlay-data-store
        so the JS bridge re-reads figure.data and refreshes the CATRED catalog."""

        @self.app.callback(
            Output("aladin-overlay-data-store", "data", allow_duplicate=True),
            Input("catred-ready-store", "data"),
            [State("view-mode-store", "data"),
             State("aladin-overlay-data-store", "data")],
            prevent_initial_call=True,
        )
        def refresh_on_catred_ready(catred_ready, mode, current_overlay):
            if not catred_ready:
                return no_update
            if not current_overlay:
                return no_update
            # Re-emit current overlay with a fresh timestamp so JS bridge sees a change.
            # The clientside figure-based rebuild will re-fire via view-mode-store or
            # relayoutData next interaction; here we just set a flag to force re-init.
            import copy
            updated = copy.copy(current_overlay) if isinstance(current_overlay, dict) else {}
            updated["_catred_ts"] = __import__("time").time()
            return updated
