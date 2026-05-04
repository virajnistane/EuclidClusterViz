"""
Tab content sections for cluster visualization app.

Contains content for File Configuration and Cluster Analysis tabs.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


class TabContent:
    """Handles tab content sections"""

    @staticmethod
    def create_file_configuration_section():
        """Create file configuration section for selecting data files"""
        return html.Div(
            [
                html.Div(
                    [
                        html.I(className="fas fa-folder-open me-2 text-primary"),
                        html.Label("Detection Catalog Configuration:", className="fw-bold mb-0"),
                    ],
                    className="d-flex align-items-center mb-3",
                ),
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                # File path display (always visible, showing current file)
                                html.Div(
                                    [
                                        html.Label(
                                            [
                                                html.I(className="fas fa-file me-2"),
                                                "Current GlueMatchCat XML File:",
                                            ],
                                            className="form-label small fw-bold",
                                        ),
                                        dbc.InputGroup(
                                            [
                                                dbc.Input(
                                                    id="gluematchcat-file-display",
                                                    type="text",
                                                    value="No file selected",
                                                    readonly=True,
                                                    className="mb-0",
                                                    style={
                                                        "border-radius": "8px 0 0 8px",
                                                        "font-size": "0.9rem",
                                                        "background-color": "#f8f9fa",
                                                    },
                                                ),
                                                dbc.Button(
                                                    html.I(className="fas fa-folder-open"),
                                                    id="browse-file-button",
                                                    color="primary",
                                                    outline=True,
                                                    size="sm",
                                                    style={
                                                        "border-radius": "0 8px 8px 0",
                                                    },
                                                    title="Browse for file",
                                                ),
                                            ],
                                            className="mb-2",
                                        ),
                                        html.Small(
                                            [
                                                html.I(className="fas fa-info-circle me-1"),
                                                "Currently loaded catalog file",
                                            ],
                                            className="text-muted",
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                # Editable file path input (for changing the file)
                                html.Div(
                                    [
                                        html.Label(
                                            [
                                                html.I(className="fas fa-edit me-2"),
                                                "Change File Path:",
                                            ],
                                            className="form-label small fw-bold",
                                        ),
                                        dbc.Input(
                                            id="gluematchcat-file-input",
                                            type="text",
                                            placeholder="Enter new path to gluematchcat XML file...",
                                            className="mb-2",
                                            style={
                                                "border-radius": "8px",
                                                "font-size": "0.9rem",
                                            },
                                        ),
                                        html.Small(
                                            [
                                                html.I(className="fas fa-info-circle me-1"),
                                                "Example: /path/to/gluematchcat_PZWAV_AMICO.xml",
                                            ],
                                            className="text-muted",
                                        ),
                                    ],
                                    id="gluematchcat-file-container",
                                    className="mb-3",
                                ),
                                # Apply button (always visible)
                                dbc.Button(
                                    [
                                        html.I(className="fas fa-check me-2"),
                                        "Apply File Configuration",
                                    ],
                                    id="apply-file-config-button",
                                    color="success",
                                    size="sm",
                                    className="w-100",
                                    disabled=True,
                                    style={"border-radius": "8px", "font-weight": "600"},
                                ),
                                # Status indicator
                                html.Div(id="file-config-status", className="mt-2 small"),
                            ]
                        )
                    ],
                    className="border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #f0fff0, #ffffff)",
                        "border-radius": "12px",
                    },
                ),
            ]
        )

    @staticmethod
    def create_cluster_analysis_tab_content():
        """Create cluster analysis tab content for the tabbed interface"""
        return html.Div(
            [
                # No cluster selected state
                html.Div(
                    [
                        html.Div(
                            [
                                html.I(className="fas fa-mouse-pointer fa-3x text-muted mb-3"),
                                html.H5("Select a Cluster", className="text-muted mb-2"),
                                html.P(
                                    "Click any cluster point on the plot to analyze",
                                    className="text-muted",
                                ),
                                html.Hr(),
                                html.P(
                                    [
                                        html.I(className="fas fa-info-circle me-2"),
                                        "Available tools: Cutouts, PHZ Analysis, Images, Export",
                                    ],
                                    className="small text-muted",
                                ),
                            ],
                            className="text-center",
                        )
                    ],
                    id="cluster-no-selection",
                    style={"padding": "60px 20px"},
                ),
                # Cluster selected state
                html.Div(
                    [
                        # Cluster info header
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    [
                                        html.H6(
                                            [
                                                html.I(className="fas fa-crosshairs me-2"),
                                                "Selected Cluster",
                                            ],
                                            className="mb-0 text-primary",
                                        )
                                    ]
                                ),
                                dbc.CardBody(
                                    [html.Div(id="cluster-info-display-tab", className="mb-3")],
                                    className="p-3",
                                ),
                            ],
                            className="mb-3",
                        ),
                        # Analysis tools
                        html.H6("🔬 Analysis Tools", className="mb-3"),
                        # Primary action buttons
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            [
                                                html.I(className="fas fa-crop me-2"),
                                                "Generate Cutout",
                                                html.I(className="fas fa-chevron-down ms-2"),
                                            ],
                                            id="tab-cutout-button",
                                            color="primary",
                                            disabled=False,
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        html.Small(
                                            "Click to see cutout options",
                                            className="text-muted d-block text-center",
                                        ),
                                    ],
                                    width=6,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            [
                                                html.I(className="fas fa-magnifying-glass me-2"),
                                                "CATRED Data Box",
                                                html.I(className="fas fa-chevron-down ms-2"),
                                            ],
                                            id="tab-catred-box-button",
                                            color="success",
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        html.Small(
                                            "Click to see box options",
                                            className="text-muted d-block text-center",
                                        ),
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
                                                html.I(className="fas fa-chevron-down ms-2"),
                                            ],
                                            id="tab-mask-cutout-button",
                                            color="info",
                                            disabled=False,
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        html.Small(
                                            "Click to see mask cutout options",
                                            className="text-muted d-block text-center",
                                        ),
                                    ],
                                    width=6,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            [
                                                html.I(className="fas fa-tag me-2"),
                                                "Tag Cluster",
                                                html.I(className="fas fa-chevron-down ms-2"),
                                            ],
                                            id="tab-tag-panel-button",
                                            color="warning",
                                            disabled=False,
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        html.Small(
                                            "Use the Candidate Tagging panel below",
                                            className="text-muted d-block text-center",
                                        ),
                                    ],
                                    width=6,
                                ),
                            ],
                            className="mb-4",
                        ),
                        # Cutout options (expandable)
                        dbc.Collapse(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(
                                            [
                                                html.H6(
                                                    [
                                                        html.I(className="fas fa-cog me-2"),
                                                        "Cutout Options",
                                                    ],
                                                    className="mb-0",
                                                )
                                            ]
                                        ),
                                        dbc.CardBody(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Size (arcmin):",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-cutout-size",
                                                                    type="number",
                                                                    value=2.0,
                                                                    min=0.0,
                                                                    max=20.0,
                                                                    step=1.0,
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
                                                                    id="tab-cutout-type",
                                                                    options=[
                                                                        {
                                                                            "label": "MER Mosaic",
                                                                            "value": "mermosaic",
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
                                                                    "Opacity (0 to 1):",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-cutout-opacity",
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
                                                                    id="tab-cutout-colorscale",
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
                                                # Cutout trace management buttons
                                                html.Div(
                                                    [
                                                        dbc.Button(
                                                            [
                                                                html.I(
                                                                    className="fas fa-play me-2"
                                                                ),
                                                                "Generate Cutout",
                                                            ],
                                                            id="tab-generate-cutout",
                                                            color="primary",
                                                            className="w-50 mb-2 me-2",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.Button(
                                                            [
                                                                html.I(className="fas fa-eye me-2"),
                                                                "Hide",
                                                            ],
                                                            id="tab-cutout-toggle-visibility",
                                                            color="secondary",
                                                            outline=True,
                                                            className="w-25 mb-2 me-2",
                                                            n_clicks=0,
                                                            disabled=True,
                                                        ),
                                                        dbc.Button(
                                                            [
                                                                html.I(
                                                                    className="fas fa-trash me-2"
                                                                ),
                                                                "Clear",
                                                            ],
                                                            id="tab-cutout-clear",
                                                            color="danger",
                                                            outline=True,
                                                            className="w-25 mb-2",
                                                            n_clicks=0,
                                                            disabled=True,
                                                        ),
                                                    ],
                                                    className="d-flex justify-content-center",
                                                ),
                                            ]
                                        ),
                                    ]
                                )
                            ],
                            id="tab-cutout-options",
                            is_open=False,
                            className="mb-3",
                        ),
                        # CATRED box options (expandable)
                        dbc.Collapse(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(
                                            [
                                                html.H6(
                                                    [
                                                        html.I(className="fas fa-cog me-2"),
                                                        "CATRED Box Options",
                                                    ],
                                                    className="mb-0",
                                                )
                                            ]
                                        ),
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
                                                                    id="tab-catred-box-size",
                                                                    type="number",
                                                                    value=2.0,
                                                                    min=1.0,
                                                                    max=10.0,
                                                                    step=1.0,
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=6,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Redshift bin width:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-catred-redshift-bin-width",
                                                                    type="number",
                                                                    value=0.5,
                                                                    min=0,
                                                                    max=3.0,
                                                                    step=0.1,
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
                                                                    "Mask Threshold:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-catred-mask-threshold",
                                                                    type="number",
                                                                    value=0.8,
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
                                                                    "Magnitude Limit:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-catred-maglim",
                                                                    type="number",
                                                                    value=24.0,
                                                                    min=20.0,
                                                                    max=32.0,
                                                                    step=1.0,
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
                                                                    "Marker Size:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Select(
                                                                    id="tab-catred-marker-size",
                                                                    options=[
                                                                        {
                                                                            "label": "Constant size",
                                                                            "value": "set_size_custom",
                                                                        },
                                                                        {
                                                                            "label": "KRON Radius",
                                                                            "value": "set_size_kronradius",
                                                                        },
                                                                    ],
                                                                    value="set_size_custom",
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Custom Size:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-catred-marker-size-custom",
                                                                    type="number",
                                                                    value=10.0,
                                                                    min=5.0,
                                                                    max=50.0,
                                                                    step=5.0,
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Marker Color:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-catred-marker-color-picker",
                                                                    type="color",
                                                                    value="#00FFF2",
                                                                    className="w-100",
                                                                    style={
                                                                        "height": "38px",
                                                                        "cursor": "pointer",
                                                                        "border-radius": "6px",
                                                                    },
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                    ]
                                                ),
                                                # CATRED box trace management buttons
                                                html.Div(
                                                    [
                                                        dbc.Button(
                                                            [
                                                                html.I(
                                                                    className="fas fa-play me-2"
                                                                ),
                                                                "View CATRED Box",
                                                            ],
                                                            id="tab-view-catred-box",
                                                            color="success",
                                                            className="w-50 mb-2 me-2",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.Button(
                                                            [
                                                                html.I(className="fas fa-eye me-2"),
                                                                "Hide",
                                                            ],
                                                            id="tab-catred-box-toggle-visibility",
                                                            color="secondary",
                                                            outline=True,
                                                            className="w-25 mb-2 me-2",
                                                            n_clicks=0,
                                                            disabled=True,
                                                        ),
                                                        dbc.Button(
                                                            [
                                                                html.I(
                                                                    className="fas fa-trash me-2"
                                                                ),
                                                                "Clear",
                                                            ],
                                                            id="tab-catred-box-clear",
                                                            color="danger",
                                                            outline=True,
                                                            className="w-25 mb-2",
                                                            n_clicks=0,
                                                            disabled=True,
                                                        ),
                                                    ],
                                                    className="d-flex justify-content-center",
                                                ),
                                            ]
                                        ),
                                    ]
                                )
                            ],
                            id="tab-catred-box-options",
                            is_open=False,
                            className="mb-3",
                        ),
                        # Mask cutout options (expandable)
                        dbc.Collapse(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(
                                            [
                                                html.H6(
                                                    [
                                                        html.I(className="fas fa-cog me-2"),
                                                        "Healpix Mask Cutout Options",
                                                    ],
                                                    className="mb-0",
                                                )
                                            ]
                                        ),
                                        dbc.CardBody(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Size (arcmin):",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-mask-cutout-size",
                                                                    type="number",
                                                                    value=2.0,
                                                                    min=0.0,
                                                                    max=20.0,
                                                                    step=1.0,
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=6,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Opacity (0 to 1):",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-mask-cutout-opacity",
                                                                    type="number",
                                                                    value=0.3,
                                                                    min=0.0,
                                                                    max=1.0,
                                                                    step=0.1,
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=6,
                                                        ),
                                                    ]
                                                ),
                                                # Mask cutout trace management buttons
                                                html.Div(
                                                    [
                                                        dbc.Button(
                                                            [
                                                                html.I(
                                                                    className="fas fa-play me-2"
                                                                ),
                                                                "Generate Mask Cutout",
                                                            ],
                                                            id="tab-generate-mask-cutout",
                                                            color="primary",
                                                            className="w-50 mb-2 me-2",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.Button(
                                                            [
                                                                html.I(className="fas fa-eye me-1"),
                                                                "Hide",
                                                            ],
                                                            id="tab-mask-cutout-toggle-visibility",
                                                            color="secondary",
                                                            outline=True,
                                                            className="w-25 mb-2 me-2",
                                                            n_clicks=0,
                                                            disabled=True,
                                                        ),
                                                        dbc.Button(
                                                            [
                                                                html.I(
                                                                    className="fas fa-trash me-1"
                                                                ),
                                                                "Clear",
                                                            ],
                                                            id="tab-mask-cutout-clear",
                                                            color="danger",
                                                            outline=True,
                                                            className="w-25 mb-2",
                                                            n_clicks=0,
                                                            disabled=True,
                                                        ),
                                                    ],
                                                    className="d-flex justify-content-center",
                                                ),
                                            ]
                                        ),
                                    ]
                                )
                            ],
                            id="tab-mask-cutout-options",
                            is_open=False,
                            className="mb-3",
                        ),
                        # Tagging options (expandable)
                        dbc.Collapse(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(
                                            [
                                                html.H6(
                                                    [
                                                        html.I(className="fas fa-tags me-2"),
                                                        "Candidate Tagging",
                                                    ],
                                                    className="mb-0 text-warning",
                                                )
                                            ]
                                        ),
                                        dbc.CardBody(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Selected Tag:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Select(
                                                                    id="tab-tag-value",
                                                                    options=[
                                                                        {
                                                                            "label": "Good",
                                                                            "value": "good",
                                                                        },
                                                                        {
                                                                            "label": "Bad",
                                                                            "value": "bad",
                                                                        },
                                                                        {
                                                                            "label": "Dubious",
                                                                            "value": "dubious",
                                                                        },
                                                                    ],
                                                                    value="good",
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Dataset Label:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tab-tag-dataset-label",
                                                                    type="text",
                                                                    placeholder="Optional label — saved as lowercase (e.g. run1, session_a)",
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=8,
                                                        ),
                                                    ],
                                                    className="g-2",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "CSV Output Path:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="tagged-clusters-output-path",
                                                                    type="text",
                                                                    placeholder="/path/to/tagged_clusters.csv",
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            width=12,
                                                        ),
                                                    ],
                                                    className="g-2",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Button(
                                                            [
                                                                html.I(className="fas fa-tag me-2"),
                                                                "Add / Update Tag",
                                                            ],
                                                            id="tab-tag-button",
                                                            color="warning",
                                                            className="me-2",
                                                            n_clicks=0,
                                                        ),
                                                        dbc.Button(
                                                            [
                                                                html.I(className="fas fa-save me-2"),
                                                                "Save Tagged CSV",
                                                            ],
                                                            id="tab-save-tagged-clusters-button",
                                                            color="secondary",
                                                            n_clicks=0,
                                                        ),
                                                    ],
                                                    className="d-flex flex-wrap gap-2 mb-2",
                                                ),
                                                html.Small(
                                                    "Tagged rows are kept in session and saved with a tag column immediately after ID_UNIQUE_CLUSTER.",
                                                    className="text-muted d-block mb-2",
                                                ),
                                                html.Div(
                                                    id="tagged-clusters-summary",
                                                    children=[
                                                        html.Small(
                                                            "No tagged clusters yet.",
                                                            className="text-muted",
                                                        )
                                                    ],
                                                ),
                                            ]
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                            ],
                            id="tab-tagging-options",
                            is_open=False,
                            className="mb-3",
                        ),
                        # Progress bar for tab actions
                        html.Div(
                            [
                                dbc.Progress(
                                    id="tab-action-progress",
                                    value=0,
                                    striped=True,
                                    animated=True,
                                    color="info",
                                    className="mb-1",
                                ),
                                html.Span("", id="tab-action-label", className="small text-muted"),
                            ],
                            id="tab-action-progress-container",
                            style={"display": "none"},
                            className="mb-2",
                        ),
                        # Analysis results area
                        html.Div(
                            [
                                html.H6("📊 Analysis Results", className="mb-2"),
                                html.Div(
                                    id="cluster-analysis-results",
                                    children=[
                                        html.P(
                                            "Analysis results will appear here",
                                            className="text-muted small",
                                        )
                                    ],
                                ),
                            ]
                        ),
                        dbc.Modal(
                            [
                                dbc.ModalHeader(
                                    dbc.ModalTitle("Tagged CSV Already Exists")
                                ),
                                dbc.ModalBody(
                                    [
                                        html.P(
                                            "The selected CSV already exists. Choose how to save the tagged cluster data."
                                        ),
                                        html.Div(id="tagged-clusters-save-conflict-message"),
                                    ]
                                ),
                                dbc.ModalFooter(
                                    [
                                        dbc.Button(
                                            "Overwrite",
                                            id="tagged-clusters-overwrite-button",
                                            color="danger",
                                            className="me-2",
                                            n_clicks=0,
                                        ),
                                        dbc.Button(
                                            "Save With Suffix",
                                            id="tagged-clusters-save-suffix-button",
                                            color="warning",
                                            className="me-2",
                                            n_clicks=0,
                                        ),
                                        dbc.Button(
                                            "Append",
                                            id="tagged-clusters-append-button",
                                            color="primary",
                                            className="me-2",
                                            n_clicks=0,
                                        ),
                                        dbc.Button(
                                            "Cancel",
                                            id="tagged-clusters-cancel-save-button",
                                            color="secondary",
                                            n_clicks=0,
                                        ),
                                    ]
                                ),
                            ],
                            id="tagged-clusters-save-conflict-modal",
                            is_open=False,
                            centered=True,
                        ),
                        dcc.Store(id="selected-cluster-merged-record", data=None),
                        dcc.Store(id="tagged-clusters-store", data=[]),
                        dcc.Store(id="tagged-clusters-pending-save", data=None),
                    ],
                    id="cluster-selected-content",
                    style={"display": "none"},
                ),
            ],
            style={"height": "60vh", "overflow-y": "auto"},
        )
