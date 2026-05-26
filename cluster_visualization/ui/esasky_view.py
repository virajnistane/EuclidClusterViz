"""
ESA Sky iframe view component.

ESA Sky is embedded as an iframe. Communication uses the official
postMessage API documented at:
https://www.cosmos.esa.int/web/esdc/esasky-javascript-api

Correct event names:
  goToRaDec        { ra, dec }
  setFov           { fov }
  overlayCatalogue { overlaySet: { overlayName, cooframe, color, skyObjectList } }
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


def create_esasky_view() -> html.Div:
    """Return the ESA Sky iframe container (hidden by default)."""
    return html.Div(
        [
            html.Iframe(
                id="esasky-iframe",
                src="about:blank",
                style={
                    "width": "100%",
                    "height": "75vh",
                    "min-height": "500px",
                    "border": "none",
                    "border-radius": "8px",
                },
                **{"allow": "fullscreen"},
            ),
            dcc.Store(id="esasky-overlay-data-store"),
            dcc.Store(id="esasky-click-store"),
            html.Span(id="esasky-postmessage-dummy", style={"display": "none"}),
            dcc.Interval(id="esasky-click-poll-interval", interval=500, disabled=True),
        ],
        id="esasky-view-container",
        style={"display": "none"},
    )


def create_view_mode_toggle() -> html.Div:
    """Return the Standard / ESA Sky view toggle placed in the header."""
    return html.Div(
        [
            dbc.ButtonGroup(
                [
                    dbc.Button(
                        [html.I(className="fas fa-chart-scatter me-1"), "Standard View"],
                        id="view-mode-plotly-btn",
                        color="primary",
                        outline=False,
                        n_clicks=0,
                        className="view-mode-btn active",
                    ),
                    dbc.Button(
                        [html.I(className="fas fa-globe me-1"), "ESA Sky View"],
                        id="view-mode-esasky-btn",
                        color="primary",
                        outline=True,
                        n_clicks=0,
                        className="view-mode-btn",
                    ),
                ],
                size="sm",
            ),
            dcc.Store(id="view-mode-store", data="plotly"),
        ],
        className="d-flex justify-content-center align-items-center mb-2",
    )
