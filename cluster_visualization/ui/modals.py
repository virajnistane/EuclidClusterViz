"""
Modal dialogs for cluster visualization app.

Contains modal windows for cluster actions and file browsing.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


class Modals:
    """Handles modal dialog components"""

    @staticmethod
    def create_cluster_action_modal():
        """Create modal dialog for cluster actions"""
        return dbc.Modal(
            [
                dbc.ModalHeader(
                    [
                        html.H4("Cluster Analysis Options", className="modal-title"),
                        dbc.Button(
                            "×", className="btn-close", id="cluster-modal-close", n_clicks=0
                        ),
                    ]
                ),
                dbc.ModalBody(
                    [
                        # Cluster information display
                        html.Div(id="cluster-modal-info", className="mb-3"),
                        # Action buttons
                        html.H6("Available Actions:", className="mb-3"),
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            [
                                                html.I(className="fas fa-crop me-2"),
                                                "Generate Cutout",
                                            ],
                                            id="cluster-cutout-button",
                                            color="primary",
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        html.Small(
                                            "Create MER mosaic cutout around this cluster",
                                            className="text-muted",
                                        ),
                                    ],
                                    width=6,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            [
                                                html.I(className="fas fa-magnifying-glass me-2"),
                                                "View CATRED Box",
                                            ],
                                            id="cluster-catred-box-button",
                                            color="success",
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        html.Small("View CATRED Box", className="text-muted"),
                                    ],
                                    width=6,
                                ),
                            ],
                            className="mb-3",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            [
                                                html.I(className="fas fa-layer-group me-2"),
                                                "Healpix Mask Cutout",
                                            ],
                                            id="cluster-healpix-mask-button",
                                            color="info",
                                            disabled=True,
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        html.Small("Coming soon ...", className="text-muted"),
                                    ],
                                    width=6,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            [html.I(className="fas fa-table me-2"), "Export Data"],
                                            id="cluster-export-button",
                                            color="warning",
                                            disabled=True,
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        html.Small(
                                            "Export cluster data and metadata",
                                            className="text-muted",
                                        ),
                                    ],
                                    width=6,
                                ),
                            ],
                            className="mb-3",
                        ),
                        # Cutout options (initially hidden)
                        dbc.Collapse(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Cutout Options"),
                                        dbc.CardBody(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Cutout Size (arcmin):",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="cutout-size-input",
                                                                    type="number",
                                                                    value=5.0,
                                                                    min=1.0,
                                                                    max=20.0,
                                                                    step=0.5,
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=6,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Data Type:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Select(
                                                                    id="cutout-data-type",
                                                                    options=[
                                                                        {
                                                                            "label": "MER Mosaic",
                                                                            "value": "mermosaic",
                                                                        },
                                                                        {
                                                                            "label": "Density Map",
                                                                            "value": "density",
                                                                        },
                                                                        {
                                                                            "label": "Both",
                                                                            "value": "both",
                                                                        },
                                                                    ],
                                                                    value="mermosaic",
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=6,
                                                        ),
                                                    ]
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Opacity:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="cutout-opacity-input",
                                                                    type="number",
                                                                    value=1.0,
                                                                    min=0.0,
                                                                    max=1.0,
                                                                    step=0.1,
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=6,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Colorscale:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Select(
                                                                    id="cutout-colorscale",
                                                                    options=[
                                                                        {
                                                                            "label": "viridis",
                                                                            "value": "viridis",
                                                                        },
                                                                        {
                                                                            "label": "gray",
                                                                            "value": "gray",
                                                                        },
                                                                        {
                                                                            "label": "plasma",
                                                                            "value": "plasma",
                                                                        },
                                                                    ],
                                                                    value="viridis",
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=6,
                                                        ),
                                                    ]
                                                ),
                                                dbc.Button(
                                                    "Generate Cutout",
                                                    id="generate-cutout-button",
                                                    color="primary",
                                                    className="w-100",
                                                    n_clicks=0,
                                                ),
                                            ]
                                        ),
                                    ]
                                )
                            ],
                            id="cutout-options-collapse",
                            is_open=False,
                        ),
                        # CATRED data box options (initially hidden)
                        dbc.Collapse(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("CATRED Data Box Options"),
                                        dbc.CardBody(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Box Size (arcmin):",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="catred-box-size-input",
                                                                    type="number",
                                                                    value=10.0,
                                                                    min=5.0,
                                                                    max=50.0,
                                                                    step=1.0,
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=6,
                                                        )
                                                    ]
                                                ),
                                                dbc.Button(
                                                    "Generate CATRED Data Box",
                                                    id="view-catred-box-button",
                                                    color="success",
                                                    className="w-100",
                                                    n_clicks=0,
                                                ),
                                            ]
                                        ),
                                    ]
                                )
                            ],
                            id="catred-box-options-collapse",
                            is_open=False,
                        ),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Close", id="cluster-modal-close-footer", color="secondary", n_clicks=0
                        )
                    ]
                ),
            ],
            id="cluster-action-modal",
            is_open=False,
            size="lg",
            backdrop=True,
            scrollable=True,
        )

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
