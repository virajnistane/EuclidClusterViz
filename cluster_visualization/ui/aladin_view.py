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
                [
                    html.Div(
                        [
                            html.Div(className="skeleton-star"),
                            html.Div(className="skeleton-star"),
                            html.Div(className="skeleton-star"),
                            html.Span("Loading sky view...", className="skeleton-label"),
                        ],
                        id="aladin-skeleton",
                        className="aladin-skeleton-overlay",
                        style={"display": "none", "position": "absolute", "inset": "0",
                               "zIndex": "10", "borderRadius": "8px"},
                    ),
                ],
                id="aladin-div",
                style={
                    "width": "100%",
                    "height": "75vh",
                    "min-height": "500px",
                    "border-radius": "8px",
                    "overflow": "hidden",
                    "position": "relative",
                },
            ),
            dcc.Store(id="aladin-overlay-data-store"),
            dcc.Store(id="aladin-click-store"),
            dcc.Store(id="viewport-cluster-count-store"),
            html.Span(id="aladin-init-dummy", style={"display": "none"}),
            dcc.Interval(id="aladin-click-poll-interval", interval=500, disabled=True),
            dcc.Interval(id="aladin-preload-interval", interval=3000, max_intervals=1, disabled=True),
        ],
        id="aladin-view-container",
        style={"display": "none"},
    )
