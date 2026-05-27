"""
View mode toggle component (Standard / Aladin Lite).
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


def create_view_mode_toggle() -> html.Div:
    """Return the Standard / Aladin view toggle placed in the header."""
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
                        [html.I(className="fas fa-star me-1"), "Aladin View"],
                        id="view-mode-aladin-btn",
                        color="primary",
                        outline=True,
                        n_clicks=0,
                        disabled=True,
                        className="view-mode-btn",
                    ),
                ],
                size="sm",
            ),
            dbc.Tooltip(
                "Zoom to exactly 1 cluster to enable Aladin view",
                target="view-mode-aladin-btn",
                placement="bottom",
            ),
            dcc.Store(id="view-mode-store", data="plotly"),
        ],
        className="d-flex justify-content-center align-items-center mb-2",
    )
