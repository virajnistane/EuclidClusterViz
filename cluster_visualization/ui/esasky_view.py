"""
View mode toggle component (Standard / Aladin Lite).
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


def create_view_mode_toggle() -> html.Div:
    """Return the Standard / Globe / Aladin view toggle placed in the header."""
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
                        [html.I(className="fas fa-globe me-1"), "Globe"],
                        id="view-mode-globe-btn",
                        color="primary",
                        outline=True,
                        n_clicks=0,
                        className="view-mode-btn",
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
                id="view-mode-btn-group",
            ),
            dbc.Tooltip(
                "Zoom to exactly 1 cluster to enable Aladin view",
                target="view-mode-aladin-btn",
                placement="bottom",
            ),
            dbc.Tooltip(
                "Whole-survey overview: cluster density and CL tiles on the sky sphere",
                target="view-mode-globe-btn",
                placement="bottom",
            ),
            dcc.Store(id="view-mode-store", data="plotly"),
        ],
        className="d-flex justify-content-center align-items-center mb-2",
    )
