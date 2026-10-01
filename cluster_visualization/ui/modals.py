"""
Modal dialogs for cluster visualization app.

Contains modal windows for cluster actions and file browsing.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


class Modals:
    """Handles modal dialog components"""

    @staticmethod
    def create_file_browser_modal():
        """Create modal dialog for browsing and selecting files"""
        return dbc.Modal(
            [
                dbc.ModalHeader(
                    [
                        html.H4("Select GlueMatchCat XML File", className="modal-title"),
                        dbc.Button("×", className="btn-close", id="file-browser-close", n_clicks=0),
                    ]
                ),
                dbc.ModalBody(
                    [
                        html.Div(
                            [
                                html.Label("Directory:", className="fw-bold mb-2"),
                                dbc.Input(
                                    id="file-browser-directory",
                                    type="text",
                                    placeholder="/path/to/directory",
                                    className="mb-3",
                                ),
                                dbc.Button(
                                    [
                                        html.I(className="fas fa-sync me-2"),
                                        "Refresh File List",
                                    ],
                                    id="file-browser-refresh",
                                    color="primary",
                                    size="sm",
                                    className="mb-3",
                                    n_clicks=0,
                                ),
                            ]
                        ),
                        html.Hr(),
                        html.Label("Available XML Files:", className="fw-bold mb-2"),
                        dbc.Spinner(
                            html.Div(
                                id="file-browser-list",
                                className="mb-3",
                                style={
                                    "max-height": "400px",
                                    "overflow-y": "auto",
                                    "border": "1px solid #dee2e6",
                                    "border-radius": "8px",
                                    "padding": "10px",
                                },
                            )
                        ),
                        dcc.Store(id="selected-file-path", data=None),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Cancel",
                            id="file-browser-cancel",
                            color="secondary",
                            n_clicks=0,
                        ),
                        dbc.Button(
                            "Select File",
                            id="file-browser-select",
                            color="primary",
                            n_clicks=0,
                            disabled=True,
                        ),
                    ]
                ),
            ],
            id="file-browser-modal",
            size="lg",
            is_open=False,
        )

    @staticmethod
    def create_getting_started_modal():
        """First-run onboarding walkthrough; reopenable via the header help button"""
        return dbc.Modal(
            [
                dbc.ModalHeader(
                    [
                        html.H4("Getting Started", className="modal-title"),
                        dbc.Button(
                            "×", className="btn-close", id="getting-started-close", n_clicks=0
                        ),
                    ]
                ),
                dbc.ModalBody(
                    [
                        html.Ol(
                            [
                                html.Li(
                                    [
                                        html.Strong("Pick your data: "),
                                        "choose the algorithm (PZWAV, AMICO or both) under Catalog, and set "
                                        "redshift, SNR and richness cuts under Filters.",
                                    ],
                                    className="mb-2",
                                ),
                                html.Li(
                                    [
                                        html.Strong("Render: "),
                                        "click Render clusters to draw the catalog. Display options then update live and keep "
                                        "your zoom; filters take effect when you press Apply filters.",
                                    ],
                                    className="mb-2",
                                ),
                                html.Li(
                                    [
                                        html.Strong("Inspect a cluster: "),
                                        "click any point on the plot to open its action modal — "
                                        "generate cutouts, load a CATRED box, or tag it good/bad/dubious.",
                                    ],
                                    className="mb-2",
                                ),
                                html.Li(
                                    [
                                        html.Strong("High-res data & imagery: "),
                                        "open the Mask (CATRED) or Mosaic section in the sidebar, set your "
                                        "options, then click that section's own button.",
                                    ],
                                    className="mb-2",
                                ),
                                html.Li(
                                    [
                                        html.Strong("Guided tours: "),
                                        "the Tutorial menu offers a one-minute quick tour, a full walkthrough, "
                                        "or a detailed tour of one section; the ? next to each sidebar section "
                                        "header starts that section's tour.",
                                    ],
                                    className="mb-2",
                                ),
                                html.Li(
                                    [
                                        html.Strong("Switch views: "),
                                        "use the Standard / Aladin toggle above the plot for a "
                                        "sky-survey-backed view of the same region.",
                                    ],
                                    className="mb-2",
                                ),
                                html.Li(
                                    [
                                        html.Strong("Status updates: "),
                                        "progress and results show as a toast top-right; click × to "
                                        "shrink it to a small dot, click the dot to bring it back.",
                                    ],
                                    className="mb-0",
                                ),
                            ],
                            className="ps-3",
                        ),
                        html.Hr(),
                        html.Small(
                            "Reopen this any time with the ? button next to the title.",
                            className="text-muted",
                        ),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Got it", id="getting-started-close-footer", color="primary", n_clicks=0
                        )
                    ]
                ),
            ],
            id="getting-started-modal",
            is_open=False,
            size="lg",
            backdrop=True,
            scrollable=True,
        )
