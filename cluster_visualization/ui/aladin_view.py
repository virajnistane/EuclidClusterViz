"""
Aladin Lite v3 viewer component.

Aladin Lite is embedded as a pure-JS viewer (CDN).  On first switch to
"aladin" mode the JS/CSS are lazy-loaded, then A.aladin() is initialised
inside #aladin-div.  All Aladin interaction (catalog overlays, click bridge)
is handled by clientside JS in ui_callbacks.py.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


def create_aladin_view() -> html.Div:
    """Return the Aladin Lite viewer container (hidden by default)."""
    return html.Div(
        [
            html.Div(
                id="aladin-div",
                style={
                    "width": "100%",
                    "height": "75vh",
                    "min-height": "500px",
                    "border-radius": "8px",
                    "overflow": "hidden",
                },
            ),
            dcc.Store(id="aladin-overlay-data-store"),
            dcc.Store(id="aladin-click-store"),
            dcc.Store(id="viewport-cluster-count-store"),
            html.Span(id="aladin-init-dummy", style={"display": "none"}),
            dcc.Interval(id="aladin-click-poll-interval", interval=500, disabled=True),
            # Fires once ~3s after page load to pre-fetch Aladin CDN assets
            dcc.Interval(id="aladin-preload-interval", interval=3000, max_intervals=1),
        ],
        id="aladin-view-container",
        style={"display": "none"},
    )
