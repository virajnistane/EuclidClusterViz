"""
App layout for cluster visualization.

Contains the main Dash layout definition orchestrating all UI components.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html

from .sidebar_sections import SidebarSections
from .tour_steps import EXTRA_TOURS, SECTION_TITLES
from .data_controls import DataControls
from .modals import Modals
from .tabs import TabContent
from .esasky_view import create_view_mode_toggle
from .aladin_view import create_aladin_view


class AppLayout:
    """Handles the main application layout orchestration"""

    @staticmethod
    def create_layout():
        """Create and return the complete app layout"""
        return dbc.Container(
            [
                # Header row
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.H1(
                                    "ESA Euclid Mission: Cluster Detection Visualization",
                                    className="text-center mb-3",
                                ),
                                html.Div(
                                    [
                                        dbc.Button(
                                            "?",
                                            id="getting-started-open",
                                            n_clicks=0,
                                            color="secondary",
                                            outline=True,
                                            size="sm",
                                            title="Getting Started",
                                            className="rounded-circle me-2",
                                        ),
                                        AppLayout._create_tutorial_menu(),
                                        html.Div(id="tour-init-dummy", style={"display": "none"}),
                                    ],
                                    className="text-center mb-2",
                                ),
                                create_view_mode_toggle(),
                            ]
                        )
                    ],
                    className="mb-3",
                ),
                # Main horizontal layout: Controls sidebar + Plot area
                dbc.Row(
                    [
                        # Left sidebar: render action, then collapsible control sections
                        dbc.Col(
                            [
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.H2("Controls", className="sidebar-title"),
                                                AppLayout._create_main_render_section(),
                                                html.P(
                                                    "Display options update live and keep your zoom. "
                                                    "Filters take effect when you press Apply filters.",
                                                    className="sidebar-note",
                                                ),
                                            ],
                                            className="sidebar-head",
                                        ),
                                        AppLayout._create_collapsible_sections(),
                                    ],
                                    className="sidebar-panel cv-panel",
                                )
                            ],
                            xs=12,
                            className="sidebar-col pe-lg-3 mb-3 mb-lg-0",
                        ),
                        # Right side: Plot area and status
                        dbc.Col(
                            [
                                # Main plots area - side by side
                                dbc.Row(
                                    [
                                        # Main cluster plot / ESA Sky viewer
                                        dbc.Col(
                                            [
                                                # Standard Plotly view
                                                html.Div(
                                                    [
                                                        dcc.Loading(
                                                            id="loading",
                                                            children=[
                                                                dcc.Graph(
                                                                    id="cluster-plot",
                                                                    style={
                                                                        "height": "75vh",
                                                                        "width": "100%",
                                                                        "min-height": "500px",
                                                                    },
                                                                    config={
                                                                        "displayModeBar": True,
                                                                        "displaylogo": False,
                                                                        "modeBarButtonsToRemove": [
                                                                            "lasso2d",
                                                                            "select2d",
                                                                        ],
                                                                        "responsive": True,
                                                                        "doubleClickDelay": 1000,
                                                                        "doubleClick": False,
                                                                    },
                                                                )
                                                            ],
                                                            type="circle",
                                                        )
                                                    ],
                                                    id="plotly-view-container",
                                                ),
                                                # Aladin Lite view (hidden until mode switch)
                                                create_aladin_view(),
                                            ],
                                            xs=12, xl=8,
                                        ),
                                        # Tabbed interface for PHZ plot and Cluster Analysis
                                        dbc.Col(
                                            [
                                                dbc.Card(
                                                    [
                                                        dbc.CardHeader(
                                                            [
                                                                dbc.Tabs(
                                                                    [
                                                                        dbc.Tab(
                                                                            label="PHZ Analysis",
                                                                            tab_id="phz-tab",
                                                                        ),
                                                                        dbc.Tab(
                                                                            label="Cluster Tools",
                                                                            tab_id="cluster-tab",
                                                                        ),
                                                                    ],
                                                                    id="analysis-tabs",
                                                                    active_tab="phz-tab",
                                                                )
                                                            ],
                                                            className="p-0",
                                                        ),
                                                        dbc.CardBody(
                                                            [
                                                                # PHZ Plot Tab Content
                                                                html.Div(
                                                                    [
                                                                        # Inner sub-tabs within PHZ Analysis
                                                                        # Content placed inside dbc.Tab children so DBC manages
                                                                        # show/hide natively (avoids empty implicit tab panes)
                                                                        dbc.Tabs(
                                                                            [
                                                                                dbc.Tab(
                                                                                    label="CATRED source",
                                                                                    tab_id="phz-catred-subtab",
                                                                                    children=[
                                                                                        dcc.Loading(
                                                                                            id="loading-phz",
                                                                                            children=[
                                                                                                dcc.Graph(
                                                                                                    id="phz-pdf-plot",
                                                                                                    style={
                                                                                                        "height": "calc(75vh - 8.5rem)",
                                                                                                        "width": "100%",
                                                                                                        "min-height": "340px",
                                                                                                    },
                                                                                                    config={
                                                                                                        "displayModeBar": "hover",
                                                                                                        "displaylogo": False,
                                                                                                        "modeBarButtonsToRemove": [
                                                                                                            "lasso2d",
                                                                                                            "select2d",
                                                                                                        ],
                                                                                                        "responsive": True,
                                                                                                    },
                                                                                                )
                                                                                            ],
                                                                                            type="circle",
                                                                                        )
                                                                                    ],
                                                                                ),
                                                                                dbc.Tab(
                                                                                    label="Cluster data",
                                                                                    tab_id="phz-cluster-subtab",
                                                                                    children=[
                                                                                        dbc.Button(
                                                                                            [
                                                                                                html.I(className="fas fa-sync-alt me-2"),
                                                                                                "Refresh (current viewport)",
                                                                                            ],
                                                                                            id="phz-cluster-refresh-btn",
                                                                                            color="primary",
                                                                                            outline=True,
                                                                                            size="sm",
                                                                                            className="mb-2 w-100",
                                                                                        ),
                                                                                        dcc.Loading(
                                                                                            id="loading-cluster-z-dist",
                                                                                            children=[
                                                                                                dcc.Graph(
                                                                                                    id="phz-cluster-z-dist-plot",
                                                                                                    style={
                                                                                                        "height": "27vh",
                                                                                                        "width": "100%",
                                                                                                        "min-height": "190px",
                                                                                                    },
                                                                                                    config={
                                                                                                        "displayModeBar": True,
                                                                                                        "displaylogo": False,
                                                                                                        "modeBarButtonsToRemove": [
                                                                                                            "lasso2d",
                                                                                                            "select2d",
                                                                                                        ],
                                                                                                        "responsive": True,
                                                                                                    },
                                                                                                )
                                                                                            ],
                                                                                            type="circle",
                                                                                        ),
                                                                                        html.Div(
                                                                                            [
                                                                                                html.Small(
                                                                                                    "Bins:",
                                                                                                    className="range-input-label mb-0 me-1",
                                                                                                ),
                                                                                                dcc.Slider(
                                                                                                    id="phz-cluster-nbins-slider",
                                                                                                    min=5,
                                                                                                    max=100,
                                                                                                    step=5,
                                                                                                    value=40,
                                                                                                    marks={5: "5", 25: "25", 50: "50", 75: "75", 100: "100"},
                                                                                                    tooltip={"placement": "bottom", "always_visible": False},
                                                                                                    className="custom-slider flex-grow-1",
                                                                                                ),
                                                                                            ],
                                                                                            className="d-flex align-items-center px-1",
                                                                                            style={"gap": "6px", "paddingBottom": "28px"},
                                                                                        ),
                                                                                        dcc.Loading(
                                                                                            id="loading-cluster-snr-z",
                                                                                            children=[
                                                                                                dcc.Graph(
                                                                                                    id="phz-cluster-snr-z-plot",
                                                                                                    style={
                                                                                                        "height": "27vh",
                                                                                                        "width": "100%",
                                                                                                        "min-height": "190px",
                                                                                                    },
                                                                                                    config={
                                                                                                        "displayModeBar": True,
                                                                                                        "displaylogo": False,
                                                                                                        "modeBarButtonsToRemove": [
                                                                                                            "lasso2d",
                                                                                                            "select2d",
                                                                                                        ],
                                                                                                        "responsive": True,
                                                                                                    },
                                                                                                )
                                                                                            ],
                                                                                            type="circle",
                                                                                        ),
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                            id="phz-inner-tabs",
                                                                            active_tab="phz-catred-subtab",
                                                                        ),
                                                                    ],
                                                                    id="phz-tab-content",
                                                                    style={"display": "block"},
                                                                ),
                                                                # Cluster Analysis Tab Content
                                                                html.Div(
                                                                    [
                                                                        TabContent.create_cluster_analysis_tab_content()
                                                                    ],
                                                                    id="cluster-tab-content",
                                                                    style={"display": "none"},
                                                                ),
                                                            ],
                                                            className="p-2",
                                                        ),
                                                    ],
                                                    className="cv-panel analysis-panel",
                                                )
                                            ],
                                            xs=12, xl=4,
                                        ),
                                    ]
                                ),
                                # Progress Bars Row - controlled by background callbacks running parameter
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            html.Span("Loading cluster data...", id="data-load-label"),
                                                            className="mb-1 small text-muted",
                                                        ),
                                                        dbc.Progress(
                                                            id="data-load-progress",
                                                            value=0,
                                                            striped=True,
                                                            animated=True,
                                                            style={"height": "8px"},
                                                        ),
                                                    ],
                                                    id="data-load-progress-container",
                                                    style={"display": "none"},
                                                    className="mb-2",
                                                ),
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            html.Span("Loading CATRED sources...", id="catred-load-label"),
                                                            className="mb-1 small text-muted",
                                                        ),
                                                        dbc.Progress(
                                                            id="catred-load-progress",
                                                            value=0,
                                                            striped=True,
                                                            animated=True,
                                                            color="warning",
                                                            style={"height": "8px"},
                                                        ),
                                                    ],
                                                    id="catred-load-progress-container",
                                                    style={"display": "none"},
                                                    className="mb-2",
                                                ),
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            html.Span("Loading mosaic tiles...", id="mosaic-load-label"),
                                                            className="mb-1 small text-muted",
                                                        ),
                                                        dbc.Progress(
                                                            id="mosaic-load-progress",
                                                            value=0,
                                                            striped=True,
                                                            animated=True,
                                                            color="info",
                                                            style={"height": "8px"},
                                                        ),
                                                    ],
                                                    id="mosaic-load-progress-container",
                                                    style={"display": "none"},
                                                    className="mb-2",
                                                ),
                                            ],
                                            className="px-3",
                                        )
                                    ],
                                    className="mt-2",
                                ),
                                # Status info row — floating toast; minimizes to a blob instead of clearing content
                                html.Div(
                                    [
                                        html.Button(
                                            "×",
                                            id="status-info-toggle",
                                            n_clicks=0,
                                            className="status-toast-toggle",
                                        ),
                                        html.Div(id="status-info"),
                                    ],
                                    id="status-toast-outer",
                                    className="status-toast-container",
                                ),
                                dcc.Store(id="status-toast-minimized-store", data=False),
                                # Slider values used by the last render, for "not applied" readouts
                                dcc.Store(id="applied-filters-store", data=None),
                                # Algorithm of the figure on screen, and where its cluster traces are,
                                # so "Apply filters" can patch only those traces
                                dcc.Store(id="rendered-meta-store", data=None),
                                dcc.Store(id="cluster-trace-index-store", data=None),
                            ],
                            xs=12,
                            className="main-col",
                        ),
                    ],
                    className="g-0",
                ),  # Remove gutters for tighter layout
                # Cluster Action Modal Dialog
                # File Browser Modal Dialog
                Modals.create_file_browser_modal(),
                # Getting Started onboarding modal
                Modals.create_getting_started_modal(),
                dcc.Store(id="onboarding-seen-store", storage_type="local", data=False),
            ],
            fluid=True,
            className="px-3",
        )

    @staticmethod
    def _create_main_render_section():
        """Primary action: render (or re-render) the catalog"""
        return dbc.Button(
            [html.I(className="fas fa-play me-2"), "Render clusters"],
            id="render-button",
            color="primary",
            className="w-100 btn-enhanced btn-primary-action",
            n_clicks=0,
        )

    @staticmethod
    def _create_collapsible_sections():
        """Sidebar sections, ordered by how often they are used"""
        return html.Div(
            [
                AppLayout._create_collapsible_card(
                    "Catalog",
                    "clusters-settings",
                    [
                        SidebarSections.create_algorithm_section(),
                        SidebarSections.create_merged_clusters_section(),
                    ],
                    icon="fa-database",
                    is_open=True,
                ),
                AppLayout._create_collapsible_card(
                    "Filters",
                    "filters-settings",
                    [
                        SidebarSections.create_redshift_section(),
                        SidebarSections.create_snr_section(),
                        SidebarSections.create_richness_section(),
                        SidebarSections.create_idcluster_section(),
                        SidebarSections.create_cluster_matching_section(),
                        SidebarSections.create_apply_filters_bar(),
                    ],
                    icon="fa-filter",
                    is_open=True,
                ),
                AppLayout._create_collapsible_card(
                    "Mask",
                    "mask-controls",
                    [
                        DataControls.create_catred_data_section(),
                        DataControls.create_healpix_mask_section(),
                    ],
                    icon="fa-border-all",
                ),
                AppLayout._create_collapsible_card(
                    "Mosaic",
                    "image-controls",
                    [DataControls.create_mosaic_controls_section()],
                    icon="fa-image",
                ),
                AppLayout._create_collapsible_card(
                    "Display",
                    "display-options",
                    [SidebarSections.create_display_options_section()],
                    icon="fa-eye",
                ),
                AppLayout._create_collapsible_card(
                    "Configuration",
                    "app-config",
                    [SidebarSections.create_config_info_section()],
                    icon="fa-cog",
                ),
            ]
        )

    @staticmethod
    def _create_tutorial_menu():
        """Tutorial menu: quick overview, full walkthrough, or one section in detail."""
        items = [
            dbc.DropdownMenuItem("Quick tour (1 min)", id="tour-quick", n_clicks=0),
            dbc.DropdownMenuItem("Full walkthrough", id="tour-full", n_clicks=0),
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem("Section in detail", header=True),
        ] + [
            dbc.DropdownMenuItem(f"{title} section", id=f"tour-section-{section}", n_clicks=0)
            for section, title in SECTION_TITLES.items()
        ] + [
            dbc.DropdownMenuItem(title, id=f"tour-{key}", n_clicks=0)
            for key, title in EXTRA_TOURS.items()
        ]
        return html.Div(
            dbc.DropdownMenu(
                items,
                label=[html.I(className="fas fa-route me-1"), "Tutorial"],
                color="secondary",
                size="sm",
                toggle_class_name="tour-menu-toggle",
                align_end=False,
            ),
            id="tutorial-tour-menu",
            className="d-inline-block",
            title="Guided tours of the app",
        )

    @staticmethod
    def _create_collapsible_card(title, card_id, content, icon, is_open=False):
        """One collapsible sidebar section; the chevron follows the open state via CSS"""
        return html.Section(
            [
                html.Div(
                    [
                        dbc.Button(
                            [
                                html.I(className="fas fa-chevron-right section-chevron"),
                                html.I(className=f"fas {icon} section-icon"),
                                html.Span(title),
                            ],
                            id=f"{card_id}-toggle",
                            color="link",
                            className="section-toggle" + (" is-open" if is_open else ""),
                            n_clicks=0,
                        ),
                        html.Button(
                            "?",
                            id=f"{card_id}-tour",
                            n_clicks=0,
                            type="button",
                            className="btn btn-sm btn-outline-secondary section-tour-btn",
                            title=f"Tour the {title} section",
                            **{"aria-label": f"Tour the {title} section"},
                        ),
                    ],
                    id=f"{card_id}-header",
                    className="section-header" + (" is-open" if is_open else ""),
                ),
                dbc.Collapse(
                    html.Div(content, className="section-body"),
                    id=f"{card_id}-collapse",
                    is_open=is_open,
                ),
            ],
            id=f"{card_id}-section",
            className="sidebar-section" + (" is-open" if is_open else ""),
        )

    @staticmethod
    def _create_file_browser_modal():
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
    def _create_cluster_analysis_tab_content():
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
                                                "Generate Cutout ...",
                                            ],
                                            id="tab-cutout-button",
                                            color="primary",
                                            disabled=False,
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        # html.Small("Click to see options", className="text-muted d-block text-center")
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
                                                "CATRED Data Box ...",
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
                                                "Healpix Mask Cutout ...",
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
                                                html.I(className="fas fa-download me-2"),
                                                "Export Data",
                                            ],
                                            id="tab-export-button",
                                            color="warning",
                                            disabled=True,
                                            className="w-100 mb-2",
                                            n_clicks=0,
                                        ),
                                        html.Small(
                                            "Coming soon ...",
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
                                                                        # {"label": "Density Map", "value": "density"},
                                                                        # {"label": "Both", "value": "both"}
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
                                                            # size="sm",
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
                                                            # size="sm",
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
                                                                        # {"label": "Both", "value": "both"}
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
                                                            # size="sm",
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
                                                            # size="sm",
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
                                                            # size="sm",
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
                                                            # size="sm",
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
                    ],
                    id="cluster-selected-content",
                    style={"display": "none"},
                ),
            ],
            style={"height": "60vh", "overflow-y": "auto"},
        )
