"""
Sidebar control sections for the cluster visualization app.

Contains all sidebar control UI components including algorithm selection,
cluster options, filtering controls, and display settings.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


class SidebarSections:
    """Handles sidebar control sections"""

    @staticmethod
    def create_algorithm_section():
        """Create algorithm selection section with enhanced styling"""
        return html.Div(
            [
                html.Div(
                    [
                        html.I(className="fas fa-cogs me-2 text-primary"),
                        html.Label("Algorithm Selection:", className="fw-bold mb-0"),
                    ],
                    className="d-flex align-items-center mb-3",
                ),
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                dcc.Dropdown(
                                    id="algorithm-dropdown",
                                    options=[
                                        {"label": "PZWAV", "value": "PZWAV"},
                                        {"label": "AMICO", "value": "AMICO"},
                                        {"label": "🌌 PZWAV & AMICO", "value": "BOTH"},
                                    ],
                                    value="PZWAV",
                                    clearable=False,
                                    style={"border-radius": "8px", "font-weight": "500"},
                                )
                            ],
                            className="p-2",
                        )
                    ],
                    className="border-0 shadow-sm mb-3",
                    style={
                        "background": "linear-gradient(45deg, #f8f9ff, #ffffff)",
                        "border-radius": "10px",
                    },
                ),
            ]
        )

    @staticmethod
    def create_merged_clusters_section():
        """Create merged clusters section"""
        return html.Div(
            [
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-layer-group me-0 text-primary"),
                                        dbc.Switch(
                                            id="merged-clusters-switch",
                                            label="Show merged catalog members",
                                            value=False,
                                            className="ms-0",
                                        ),
                                    ],
                                    className="d-flex align-items-left mb-0",
                                ),
                                html.Small(
                                    [
                                        html.I(className="fas fa-info-circle me-0"),
                                        "Cluster detections from Merge_Cl code, merged over Cluster-Tiles",
                                    ],
                                    className="text-muted ms-0",
                                ),
                            ]
                        )
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #f0f8ff, #ffffff)",
                        "border-radius": "10px",
                    },
                )
            ]
        )

    @staticmethod
    def create_cluster_matching_section():
        """Create cluster matching section with enhanced styling"""
        return html.Div(
            [
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-object-group me-0 text-primary"),
                                        dbc.Switch(
                                            id="matching-clusters-switch",
                                            label="Show matched clusters (CAT-CL)",
                                            value=False,
                                            disabled=True,
                                            className="ms-0",
                                        ),
                                        html.Button(
                                            [html.I(className="fas fa-sync-alt me-1"), "Render"],
                                            id="rerender-ovals-button",
                                            className="btn btn-sm btn-outline-primary ms-2",
                                            style={
                                                "fontSize": "0.75rem",
                                                "padding": "0.25rem 0.5rem",
                                            },
                                            title="Re-render ovals for current zoom window",
                                        ),
                                    ],
                                    className="d-flex align-items-center mb-0",
                                ),
                                html.Small(
                                    [
                                        html.I(className="fas fa-info-circle me-0"),
                                        "Ovals show in viewport only - zoom in, then re-render",
                                    ],
                                    className="text-muted ms-0",
                                ),
                            ]
                        )
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #f0f8ff, #ffffff)",
                        "border-radius": "10px",
                    },
                )
            ]
        )

    @staticmethod
    def create_snr_section():
        """Create SNR filtering section with enhanced styling"""

        snr_pzwav_tab = dbc.Card(
            [
                dbc.CardBody(
                    [
                        # SNR range display badge
                        dbc.Badge(
                            id="snr-range-display-pzwav",
                            color="light",
                            className="w-100 mb-3 p-2 fs-6 badge-enhanced status-indicator",
                            style={
                                "background": "linear-gradient(45deg, #e8f5e8, #f0f8f0)",
                                "color": "#2d5a2d",
                                "border-radius": "8px",
                                "border": "1px solid rgba(46, 204, 113, 0.3)",
                            },
                        ),
                        # SNR range slider
                        html.Div(
                            [
                                dcc.RangeSlider(
                                    id="snr-range-slider-pzwav",
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    marks={},
                                    value=[0, 100],
                                    tooltip={
                                        "placement": "bottom",
                                        "always_visible": False,
                                        "style": {"fontSize": "12px"},
                                    },
                                    allowCross=False,
                                    className="custom-range-slider",
                                )
                            ],
                            className="mb-1",
                            style={"padding": "10px 15px", "margin": "5px 0", "minHeight": "60px"},
                        ),
                        # Apply button
                        dbc.Button(
                            [html.I(className="fas fa-filter me-2"), "Apply SNR Filter (PZWAV)"],
                            id="snr-render-button-pzwav",
                            color="success",
                            size="sm",
                            className="w-100 shadow-sm btn-enhanced",
                            n_clicks=0,
                            disabled=True,
                            style={"border-radius": "8px", "font-weight": "600"},
                        ),
                    ],
                    className="p-3",
                )
            ],
            className="border-0 shadow-sm mb-3",
            style={
                "background": "linear-gradient(135deg, #f0fff0, #ffffff)",
                "border-radius": "12px",
            },
        )

        snr_amico_tab = dbc.Card(
            [
                dbc.CardBody(
                    [
                        # SNR range display badge
                        dbc.Badge(
                            id="snr-range-display-amico",
                            color="light",
                            className="w-100 mb-3 p-2 fs-6 badge-enhanced status-indicator",
                            style={
                                "background": "linear-gradient(45deg, #e8f5e8, #f0f8f0)",
                                "color": "#2d5a2d",
                                "border-radius": "8px",
                                "border": "1px solid rgba(46, 204, 113, 0.3)",
                            },
                        ),
                        # SNR range slider
                        html.Div(
                            [
                                dcc.RangeSlider(
                                    id="snr-range-slider-amico",
                                    min=0,
                                    max=100,
                                    step=0.1,
                                    marks={},
                                    value=[0, 100],
                                    tooltip={
                                        "placement": "bottom",
                                        "always_visible": False,
                                        "style": {"fontSize": "12px"},
                                    },
                                    allowCross=False,
                                    className="custom-range-slider",
                                )
                            ],
                            className="mb-1",
                            style={"padding": "10px 15px", "margin": "5px 0", "minHeight": "60px"},
                        ),
                        # Apply button
                        dbc.Button(
                            [html.I(className="fas fa-filter me-2"), "Apply SNR Filter (AMICO)"],
                            id="snr-render-button-amico",
                            color="success",
                            size="sm",
                            className="w-100 shadow-sm btn-enhanced",
                            n_clicks=0,
                            disabled=True,
                            style={"border-radius": "8px", "font-weight": "600"},
                        ),
                    ],
                    className="p-3",
                )
            ],
            className="border-0 shadow-sm mb-3",
            style={
                "background": "linear-gradient(135deg, #f0fff0, #ffffff)",
                "border-radius": "12px",
            },
        )

        return html.Div(
            [
                html.Div(
                    [
                        html.I(className="fas fa-signal me-1 text-success"),
                        html.Label("SNR Filtering:", className="fw-bold mb-1"),
                    ],
                    className="d-flex align-items-left mb-0",
                ),
                dbc.Tabs(
                    [
                        dbc.Tab(label="PZWAV", children=[snr_pzwav_tab]),
                        dbc.Tab(label="AMICO", children=[snr_amico_tab]),
                    ]
                ),
            ]
        )

    @staticmethod
    def create_redshift_section():
        """Create redshift filtering section with enhanced styling"""
        return html.Div(
            [
                html.Div(
                    [
                        html.I(className="fas fa-expand-arrows-alt me-1 text-danger"),
                        html.Label("Redshift Filtering:", className="fw-bold mb-1"),
                    ],
                    className="d-flex align-items-left mb-0",
                ),
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                # Redshift range display badge
                                dbc.Badge(
                                    id="redshift-range-display",
                                    color="light",
                                    className="w-100 mb-3 p-2 fs-6 badge-enhanced status-indicator",
                                    style={
                                        "background": "linear-gradient(45deg, #ffe8e8, #fff0f0)",
                                        "color": "#5a2d2d",
                                        "border-radius": "8px",
                                        "border": "1px solid rgba(231, 76, 60, 0.3)",
                                    },
                                ),
                                # Redshift range slider
                                html.Div(
                                    [
                                        dcc.RangeSlider(
                                            id="redshift-range-slider",
                                            min=0,
                                            max=10,
                                            step=0.1,
                                            marks={},
                                            value=[0, 10],
                                            tooltip={
                                                "placement": "bottom",
                                                "always_visible": False,
                                                "style": {"fontSize": "12px"},
                                            },
                                            allowCross=False,
                                            className="custom-range-slider",
                                        )
                                    ],
                                    className="mb-1",
                                    style={
                                        "padding": "10px 15px",
                                        "margin": "5px 0",
                                        "minHeight": "60px",
                                    },
                                ),
                                # Apply button
                                dbc.Button(
                                    [
                                        html.I(className="fas fa-filter me-2"),
                                        "Apply Redshift Filter",
                                    ],
                                    id="redshift-render-button",
                                    color="danger",
                                    size="sm",
                                    className="w-100 shadow-sm btn-enhanced",
                                    n_clicks=0,
                                    disabled=True,
                                    style={"border-radius": "8px", "font-weight": "600"},
                                ),
                            ],
                            className="p-3",
                        )
                    ],
                    className="border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(135deg, #fff0f0, #ffffff)",
                        "border-radius": "12px",
                    },
                ),
            ]
        )
    
    @staticmethod
    def create_idcluster_section():
        """Create cluster-ID based filtering section with enhanced styling"""
        return html.Div(
            [
                html.Div(
                    [
                        html.I(className="fas fa-id-badge me-1 text-danger"),
                        html.Label("Cluster-ID based Filtering:", className="fw-bold mb-1"),
                    ],
                    className="d-flex align-items-left mb-0",
                ),
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                dbc.Badge(
                                    id="idcluster-status-display",
                                    color="light",
                                    className="w-100 mb-2 p-2 fs-6",
                                    style={
                                        "background": "linear-gradient(45deg, #ffe8e8, #fff0f0)",
                                        "color": "#5a2d2d",
                                        "border-radius": "8px",
                                        "border": "1px solid rgba(231, 76, 60, 0.3)",
                                        "fontSize": "0.75rem",
                                    },
                                    children="No ID list uploaded",
                                ),
                                # Cluster-ID file selector
                                html.Div(
                                    [
                                        dcc.Upload(
                                            id="idcluster-upload",
                                            children=html.Div(
                                                [
                                                    html.I(className="fas fa-upload me-2"),
                                                    "Upload"
                                                ]
                                            ),
                                            accept=".txt,.csv",
                                            style={
                                                "width": "100%",
                                                "height": "40px",
                                                "lineHeight": "40px",
                                                "borderWidth": "1px",
                                                "borderStyle": "dashed",
                                                "borderRadius": "8px",
                                                "textAlign": "center",
                                                "backgroundColor": "#fff0f0",
                                                "borderColor": "#e74c3c",
                                                "color": "#e74c3c",
                                                "fontWeight": "500",
                                            },
                                            multiple=False,
                                        ),
                                        html.Small(
                                            "Cluster-ID List (.txt or .csv, one ID per line)",
                                            className="text-muted d-block me-1",
                                            style={
                                                "fontSize": "1rem", 
                                                "marginTop": "5px",
                                                "textAlign": "center",
                                                },
                                        ),
                                    ],
                                    className="mb-1",
                                    style={
                                        "padding": "5px 20px",
                                        "margin": "10px 0",
                                        "minHeight": "60px",
                                    },
                                ),
                                # Apply button
                                dbc.Button(
                                    [
                                        html.I(className="fas fa-filter me-2"),
                                        "Apply Cluster-ID Filter",
                                    ],
                                    id="idcluster-render-button",
                                    color="danger",
                                    size="sm",
                                    className="w-100 shadow-sm btn-enhanced",
                                    n_clicks=0,
                                    disabled=True,
                                    style={"border-radius": "8px", "font-weight": "600"},
                                ),
                            ],
                            className="p-4",
                        )
                    ],
                    className="border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(135deg, #fff0f0, #ffffff)",
                        "border-radius": "12px",
                    },
                ),
            ]
        )


    @staticmethod
    def create_display_options_section():
        """Create display options section with enhanced styling"""
        return html.Div(
            [
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-shapes me-0 text-info"),
                                        dbc.Switch(
                                            id="polygon-switch",
                                            label="Fill CL-tiles (CORE) polygons",
                                            value=False,
                                            className="ms-0",
                                        ),
                                    ],
                                    className="d-flex align-items-left mb-1",
                                )
                            ]
                        )
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #e8f8f8, #ffffff)",
                        "border-radius": "10px",
                    },
                ),
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-th me-0 text-warning"),
                                        dbc.Switch(
                                            id="mer-switch",
                                            label="Show MER tiles (up to LEV2 in CL-tiles)",
                                            value=True,
                                            className="ms-0",
                                        ),
                                    ],
                                    className="d-flex align-items-left mb-1",
                                ),
                                html.Small(
                                    [
                                        html.I(className="fas fa-info-circle me-1"),
                                        "Only with open cluster-tile polygons",
                                    ],
                                    className="text-muted ms-0",
                                ),
                            ]
                        )
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #fff8e1, #ffffff)",
                        "border-radius": "10px",
                    },
                ),
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-expand me-0 text-success"),
                                        dbc.Switch(
                                            id="aspect-ratio-switch",
                                            label="Free aspect ratio",
                                            value=True,
                                            className="ms-0",
                                        ),
                                    ],
                                    className="d-flex align-items-left mb-1",
                                ),
                                html.Small(
                                    [
                                        html.I(className="fas fa-info-circle me-1"),
                                        "Default: maintain astronomical aspect",
                                    ],
                                    className="text-muted ms-0",
                                ),
                            ]
                        )
                    ],
                    className="border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #e8f5e8, #ffffff)",
                        "border-radius": "10px",
                    },
                ),
            ]
        )

    @staticmethod
    def create_config_info_section():
        """Create application configuration info section"""
        return html.Div(
            [
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.Div(
                                    [
                                        html.I(className="fas fa-database me-2 text-primary"),
                                        html.Strong("Merged Catalog:", className="me-2"),
                                    ],
                                    className="d-flex align-items-center mb-2",
                                ),
                                html.Div(
                                    id="config-merged-catalog",
                                    className="mb-3 small",
                                    children=[
                                        html.Div(
                                            [
                                                dbc.Spinner(size="sm", color="primary"),
                                                html.Span(" Loading...", className="ms-2"),
                                            ]
                                        )
                                    ],
                                ),
                                html.Hr(className="my-2"),
                                html.Div(
                                    [
                                        html.I(className="fas fa-file-alt me-2 text-info"),
                                        html.Strong("Tile Detection List:", className="me-2"),
                                    ],
                                    className="d-flex align-items-center mb-2",
                                ),
                                html.Div(
                                    id="config-detintile-list",
                                    className="mb-2 small",
                                    children=[
                                        html.Div(
                                            [
                                                dbc.Spinner(size="sm", color="primary"),
                                                html.Span(" Loading...", className="ms-2"),
                                            ]
                                        )
                                    ],
                                ),
                            ],
                            className="p-3",
                        )
                    ],
                    className="mb-3 border-0 shadow-sm",
                    style={
                        "background": "linear-gradient(45deg, #f0f4ff, #ffffff)",
                        "border-radius": "12px",
                    },
                )
            ]
        )
