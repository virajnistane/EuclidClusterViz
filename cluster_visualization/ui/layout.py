"""
App layout for cluster visualization.

Contains the complete Dash layout definition with sidebar controls,
main plot area, and PHZ_PDF plot in a responsive design.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


class AppLayout:
    """Handles the main application layout"""
    
    @staticmethod
    def create_layout():
        """Create and return the complete app layout"""
        return dbc.Container([
            # Header row
            dbc.Row([
                dbc.Col([
                    html.H1("ESA Euclid Mission: Cluster Detection Visualization", className="text-center mb-3"),
                ])
            ], className="mb-3"),
            
            # Main horizontal layout: Controls sidebar + Plot area
            dbc.Row([
                # Left sidebar with controls
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H5("Visualization Controls", className="mb-0 text-center")
                        ]),
                        dbc.CardBody([
                            html.P("Options update in real-time while preserving zoom", 
                                   className="text-muted small mb-3 text-center"),
                            
                            
                            # Main render button
                            AppLayout._create_main_render_section(),

                            html.Hr(),

                            # Algorithm selection
                            AppLayout._create_algorithm_section(),
                            
                            # SNR Filtering section
                            AppLayout._create_snr_section(),
                            
                            # Redshift Filtering section
                            AppLayout._create_redshift_section(),
                            
                            # Display options
                            AppLayout._create_display_options_section(),
                            
                            # High-res CATRED data
                            AppLayout._create_catred_data_section(),
                            
                            # Mosaic image controls
                            AppLayout._create_mosaic_controls_section(),
                            
                        ])
                    ], className="h-100")
                ], width=2, className="pe-2"),
                
                # Right side: Plot area and status
                dbc.Col([
                    # Main plots area - side by side
                    dbc.Row([
                        # Main cluster plot
                        dbc.Col([
                            dcc.Loading(
                                id="loading",
                                children=[
                                    dcc.Graph(
                                        id='cluster-plot',
                                        style={'height': '75vh', 'width': '100%', 'min-height': '500px'},
                                        config={
                                            'displayModeBar': True,
                                            'displaylogo': False,
                                            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                                            'responsive': True
                                        }
                                    )
                                ],
                                type="circle"
                            )
                        ], width=8),
                        
                        # Tabbed interface for PHZ plot and Cluster Analysis
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader([
                                    dbc.Tabs([
                                        dbc.Tab(label="📈 PHZ Analysis", tab_id="phz-tab"),
                                        dbc.Tab(label="🎯 Cluster Tools", tab_id="cluster-tab")
                                    ], id="analysis-tabs", active_tab="phz-tab")
                                ], className="p-0"),
                                dbc.CardBody([
                                    # PHZ Plot Tab Content
                                    html.Div([
                                        dcc.Loading(
                                            id="loading-phz",
                                            children=[
                                                dcc.Graph(
                                                    id='phz-pdf-plot',
                                                    style={'height': '65vh', 'width': '100%', 'min-height': '450px'},
                                                    config={
                                                        'displayModeBar': True,
                                                        'displaylogo': False,
                                                        'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'pan2d', 'zoom2d', 'autoScale2d', 'resetScale2d'],
                                                        'responsive': True
                                                    }
                                                )
                                            ],
                                            type="circle"
                                        )
                                    ], id="phz-tab-content", style={'display': 'block'}),
                                    
                                    # Cluster Analysis Tab Content
                                    html.Div([
                                        AppLayout._create_cluster_analysis_tab_content()
                                    ], id="cluster-tab-content", style={'display': 'none'})
                                ], className="p-2")
                            ], style={'height': '75vh'})
                        ], width=4)
                    ]),
                    
                    # Status info row
                    dbc.Row([
                        dbc.Col([
                            html.Div(id="status-info", className="mt-2")
                        ])
                    ])
                ], width=10)
            ], className="g-0"),  # Remove gutters for tighter layout
            
            # Cluster Action Modal Dialog
            AppLayout._create_cluster_action_modal()
            
        ], fluid=True, className="px-3")
    
    @staticmethod
    def _create_algorithm_section():
        """Create algorithm selection section"""
        return html.Div([
            html.Label("Algorithm:", className="fw-bold mb-2 text-primary"),
            dcc.Dropdown(
                id='algorithm-dropdown',
                options=[
                    {'label': 'PZWAV', 'value': 'PZWAV'},
                    {'label': 'AMICO', 'value': 'AMICO'}
                ],
                value='PZWAV',
                clearable=False
            )
        ], className="mb-4")
    
    @staticmethod
    def _create_snr_section():
        """Create SNR filtering section"""
        return html.Div([
            html.Label("SNR Filtering:", className="fw-bold mb-2 text-primary"),
            html.Div(id="snr-range-display", className="text-center mb-2"),
            dcc.RangeSlider(
                id='snr-range-slider',
                min=0,  # Will be updated dynamically
                max=100,  # Will be updated dynamically
                step=0.1,
                marks={},  # Will be updated dynamically
                value=[0, 100],  # Will be updated dynamically
                tooltip={"placement": "bottom", "always_visible": True},
                allowCross=False
            ),
            dbc.Button(
                "Apply SNR Filter",
                id="snr-render-button",
                color="secondary",
                size="sm",
                className="w-100 mt-2",
                n_clicks=0,
                disabled=True
            )
        ], className="mb-4")
    
    @staticmethod
    def _create_redshift_section():
        """Create redshift filtering section"""
        return html.Div([
            html.Label("Redshift Filtering:", className="fw-bold mb-2 text-primary"),
            html.Div(id="redshift-range-display", className="text-center mb-2"),
            dcc.RangeSlider(
                id='redshift-range-slider',
                min=0,  # Will be updated dynamically
                max=10,  # Will be updated dynamically
                step=0.1,
                marks={},  # Will be updated dynamically
                value=[0, 10],  # Will be updated dynamically
                tooltip={"placement": "bottom", "always_visible": True},
                allowCross=False,
            ),
            dbc.Button(
                "Apply redshift Filter",
                id="redshift-render-button",
                color="secondary",
                size="sm",
                className="w-100 mt-2",
                n_clicks=0,
                disabled=True
            )
        ], className="mb-4")
    
    @staticmethod
    def _create_display_options_section():
        """Create display options section"""
        return html.Div([
            html.Label("Display Options:", className="fw-bold mb-2 text-primary"),
            
            html.Div([
                dbc.Switch(
                    id="merged-clusters-switch",
                    label="Show merged catalog members",
                    value=True,
                ),
                html.Small("(Toggle to access individual tile clusters underneath)", className="text-muted")
            ], className="mb-2"),
            
            html.Div([
                dbc.Switch(
                    id="polygon-switch",
                    label="Fill CL-tiles (CORE) polygons",
                    value=False,
                )
            ], className="mb-2"),
            
            html.Div([
                dbc.Switch(
                    id="mer-switch",
                    label="Show MER tiles (up to LEV2 in CL-tiles)",
                    value=True,
                ),
                html.Small("(Only with unfilled cluster-tile polygons)", className="text-muted")
            ], className="mb-2"),
            
            html.Div([
                dbc.Switch(
                    id="aspect-ratio-switch",
                    label="Free aspect ratio",
                    value=True,
                ),
                html.Small("(Default: maintain astronomical aspect)", className="text-muted")
            ], className="mb-2"),
            
        ], className="mb-4")
    
    @staticmethod
    def _create_catred_data_section():
        """Create High-res CATRED data section"""
        return html.Div([
            html.Label("High-res CATRED data:", className="fw-bold mb-2 text-primary"),
            dbc.Switch(
                id="catred-mode-switch",
                label="Masked CATRED data",
                value=True,
            ),
            html.Small("(When zoomed < 2°)", className="text-muted"),
            
            # Threshold slider for masked CATRED data
            html.Div([
                html.Div([
                    html.Label("Effective Coverage Threshold:", className="fw-bold mb-2"),
                    dcc.Slider(
                        id="catred-threshold-slider",
                        min=0.0,
                        max=0.99,
                        step=0.01,
                        value=0.8,
                        marks={
                            0.0: "0.0",
                            0.2: "0.2",
                            0.4: "0.4", 
                            0.6: "0.6",
                            0.8: "0.8",
                            0.99: "0.99"
                        },
                        tooltip={"placement": "bottom", "always_visible": True}
                    ),
                    html.Small("(For masked CATRED data filtering)", className="text-muted")
                ], id="catred-threshold-container", className="mb-3"),
            ]),
            
            # Magnitude limit slider for CATRED data
            html.Div([
                html.Div([
                    html.Label("Magnitude Limit (H-band):", className="fw-bold mb-2"),
                    dcc.Slider(
                        id="magnitude-limit-slider",
                        min=20.0,
                        max=32.0,
                        step=0.1,
                        value=24.0,
                        marks={
                            20.0: "20.0",
                            22.0: "22.0",
                            24.0: "24.0",
                            26.0: "26.0",
                            28.0: "28.0",
                            30.0: "30.0",
                            32.0: "32.0"
                        },
                        tooltip={"placement": "bottom", "always_visible": True}
                    ),
                    html.Small("(Keep sources brighter than limit)", className="text-muted")
                ], id="magnitude-limit-container", className="mb-3"),
            ]),
            
            # CATRED Data Controls (within High-res CATRED data section)
            html.Div([
                html.Div([
                    html.Label("CATRED Data Controls:", className="fw-bold mb-2"),
                    
                    html.Div([
                        dbc.Button(
                            "🔍 Render CATRED Data",
                            id="catred-render-button",
                            color="info",
                            size="sm",
                            className="w-100 mb-2",
                            n_clicks=0,
                            disabled=True
                        ),
                        html.Small("(Zoom in first, then click)", className="text-muted d-block text-center mb-3")
                    ]),
                    
                    html.Div([
                        dbc.Button(
                            "🗑️ Clear All CATRED Data",
                            id="catred-clear-button",
                            color="warning",
                            size="sm",
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("(Remove all CATRED traces)", className="text-muted d-block text-center")
                    ])
                ], id="catred-controls-container", className="mb-3"),
            ]),
        ], className="mb-4")
    
    @staticmethod
    def _create_mosaic_controls_section():
        """Create mosaic image controls section"""
        return html.Div([
            html.Label("Mosaic Image Controls:", className="fw-bold mb-2 text-primary"),
            
            html.Div([
                dbc.Switch(
                    id="mosaic-enable-switch",
                    label="Enable mosaic images",
                    value=True,
                )
            ], className="mb-2"),
            
            html.Div([
                html.Label("Mosaic Opacity:", className="fw-bold mb-1"),
                dcc.Slider(
                    id="mosaic-opacity-slider",
                    min=0.1,
                    max=1.0,
                    step=0.1,
                    value=0.7,
                    marks={0.1: '10%', 0.5: '50%', 1.0: '100%'},
                    tooltip={"placement": "bottom", "always_visible": False}
                )
            ], className="mb-2"),
            
            html.Div([
                dbc.Button(
                    "🖼️ Load Mosaic in Zoom",
                    id="mosaic-render-button",
                    color="info",
                    size="sm",
                    className="w-100 mb-2",
                    n_clicks=0,
                    disabled=True
                ),
                html.Small("(Load mosaic images for visible MER tiles)", className="text-muted d-block text-center")
            ])
        ], className="mb-4")
    
    @staticmethod
    def _create_main_render_section():
        """Create main render button section"""
        return html.Div([
            dbc.Button(
                "🚀 Initial Render",
                id="render-button",
                color="primary",
                size="lg",
                className="w-100 mb-2",
                n_clicks=0
            ),
            html.Small("After initial render, options update automatically", 
                      className="text-muted d-block text-center")
        ])

    @staticmethod
    def _create_cluster_action_modal():
        """Create modal dialog for cluster actions"""
        return dbc.Modal([
            dbc.ModalHeader([
                html.H4("Cluster Analysis Options", className="modal-title"),
                dbc.Button("×", className="btn-close", id="cluster-modal-close", n_clicks=0)
            ]),
            dbc.ModalBody([
                # Cluster information display
                html.Div(id="cluster-modal-info", className="mb-3"),
                
                # Action buttons
                html.H6("Available Actions:", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-crop me-2"), "Generate Cutout"],
                            id="cluster-cutout-button",
                            color="primary",
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("Create density map cutout around this cluster", className="text-muted")
                    ], width=6),
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-chart-line me-2"), "Analyze PHZ"],
                            id="cluster-phz-button", 
                            color="info",
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("Photometric redshift analysis", className="text-muted")
                    ], width=6)
                ], className="mb-3"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-images me-2"), "View Images"],
                            id="cluster-images-button",
                            color="success", 
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("View related astronomical images", className="text-muted")
                    ], width=6),
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-table me-2"), "Export Data"],
                            id="cluster-export-button",
                            color="warning",
                            className="w-100 mb-2", 
                            n_clicks=0
                        ),
                        html.Small("Export cluster data and metadata", className="text-muted")
                    ], width=6)
                ], className="mb-3"),
                
                # Cutout options (initially hidden)
                dbc.Collapse([
                    dbc.Card([
                        dbc.CardHeader("Cutout Options"),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Cutout Size (arcmin):", className="form-label"),
                                    dbc.Input(
                                        id="cutout-size-input",
                                        type="number",
                                        value=5.0,
                                        min=1.0,
                                        max=20.0,
                                        step=0.5,
                                        className="mb-2"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Data Type:", className="form-label"),
                                    dbc.Select(
                                        id="cutout-data-type",
                                        options=[
                                            {"label": "Density Map", "value": "density"},
                                            {"label": "Sky Image", "value": "sky"},
                                            {"label": "Both", "value": "both"}
                                        ],
                                        value="density",
                                        className="mb-2"
                                    )
                                ], width=6)
                            ]),
                            dbc.Button(
                                "Generate Cutout",
                                id="generate-cutout-button",
                                color="primary",
                                className="w-100",
                                n_clicks=0
                            )
                        ])
                    ])
                ], id="cutout-options-collapse", is_open=False)
            ]),
            dbc.ModalFooter([
                dbc.Button("Close", id="cluster-modal-close-footer", color="secondary", n_clicks=0)
            ])
        ], 
        id="cluster-action-modal", 
        is_open=False, 
        size="lg",
        backdrop=True,
        scrollable=True)

    @staticmethod
    def _create_cluster_analysis_tab_content():
        """Create cluster analysis tab content for the tabbed interface"""
        return html.Div([
            # No cluster selected state
            html.Div([
                html.Div([
                    html.I(className="fas fa-mouse-pointer fa-3x text-muted mb-3"),
                    html.H5("Select a Cluster", className="text-muted mb-2"),
                    html.P("Click any cluster point on the plot to analyze", className="text-muted"),
                    html.Hr(),
                    html.P([
                        html.I(className="fas fa-info-circle me-2"),
                        "Available tools: Cutouts, PHZ Analysis, Images, Export"
                    ], className="small text-muted")
                ], className="text-center")
            ], id="cluster-no-selection", style={'padding': '60px 20px'}),
            
            # Cluster selected state
            html.Div([
                # Cluster info header
                dbc.Card([
                    dbc.CardHeader([
                        html.H6([
                            html.I(className="fas fa-crosshairs me-2"),
                            "Selected Cluster"
                        ], className="mb-0 text-primary")
                    ]),
                    dbc.CardBody([
                        html.Div(id="cluster-info-display-tab", className="mb-3")
                    ], className="p-3")
                ], className="mb-3"),
                
                # Analysis tools
                html.H6("🔬 Analysis Tools", className="mb-3"),
                
                # Primary action buttons
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-crop me-2"), "Generate Cutout"],
                            id="tab-cutout-button",
                            color="primary",
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("Density map cutout around cluster", className="text-muted d-block text-center")
                    ], width=6),
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-chart-line me-2"), "PHZ Analysis"],
                            id="tab-phz-button",
                            color="info",
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("Photometric redshift analysis", className="text-muted d-block text-center")
                    ], width=6)
                ], className="mb-3"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-images me-2"), "View Images"],
                            id="tab-images-button",
                            color="success",
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("Related astronomical images", className="text-muted d-block text-center")
                    ], width=6),
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-download me-2"), "Export Data"],
                            id="tab-export-button",
                            color="warning",
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("Export cluster data & metadata", className="text-muted d-block text-center")
                    ], width=6)
                ], className="mb-4"),
                
                # Cutout options (expandable)
                dbc.Collapse([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H6([
                                html.I(className="fas fa-cog me-2"),
                                "Cutout Options"
                            ], className="mb-0")
                        ]),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Size (arcmin):", className="form-label"),
                                    dbc.Input(
                                        id="tab-cutout-size",
                                        type="number",
                                        value=5.0,
                                        min=1.0,
                                        max=20.0,
                                        step=0.5,
                                        className="mb-2"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Data Type:", className="form-label"),
                                    dbc.Select(
                                        id="tab-cutout-type",
                                        options=[
                                            {"label": "Density Map", "value": "density"},
                                            {"label": "Sky Image", "value": "sky"},
                                            {"label": "Both", "value": "both"}
                                        ],
                                        value="density",
                                        className="mb-2"
                                    )
                                ], width=6)
                            ]),
                            dbc.Button(
                                [html.I(className="fas fa-play me-2"), "Generate Cutout"],
                                id="tab-generate-cutout",
                                color="primary",
                                className="w-100",
                                n_clicks=0
                            )
                        ])
                    ])
                ], id="tab-cutout-options", is_open=False, className="mb-3"),
                
                # Analysis results area
                html.Div([
                    html.H6("📊 Analysis Results", className="mb-2"),
                    html.Div(id="cluster-analysis-results", children=[
                        html.P("Analysis results will appear here", className="text-muted small")
                    ])
                ])
                
            ], id="cluster-selected-content", style={'display': 'none'})
            
        ], style={'height': '60vh', 'overflow-y': 'auto'})

    @staticmethod
    def _create_cluster_analysis_section():
        """Create cluster analysis section"""
        return html.Div([
            html.H6("🎯 Cluster Analysis", className="text-primary mb-3"),
            
            # Cluster selection info (initially hidden)
            dbc.Collapse([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6("📍 Selected Cluster", className="mb-0 text-success")
                    ]),
                    dbc.CardBody([
                        html.Div(id="cluster-info-display", className="mb-3"),
                        
                        # Quick action buttons
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="fas fa-crop me-1"), "Cutout"],
                                    id="quick-cutout-button",
                                    color="primary",
                                    size="sm",
                                    className="w-100 mb-1",
                                    n_clicks=0
                                )
                            ], width=6),
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="fas fa-chart-line me-1"), "PHZ"],
                                    id="quick-phz-button",
                                    color="info", 
                                    size="sm",
                                    className="w-100 mb-1",
                                    n_clicks=0
                                )
                            ], width=6)
                        ]),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="fas fa-images me-1"), "Images"],
                                    id="quick-images-button",
                                    color="success",
                                    size="sm", 
                                    className="w-100 mb-1",
                                    n_clicks=0
                                )
                            ], width=6),
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="fas fa-cog me-1"), "More..."],
                                    id="cluster-more-options-button",
                                    color="secondary",
                                    size="sm",
                                    className="w-100 mb-1",
                                    n_clicks=0
                                )
                            ], width=6)
                        ]),
                        
                        # Expandable detailed options
                        dbc.Collapse([
                            html.Hr(className="my-2"),
                            html.H6("Cutout Options:", className="mb-2"),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Size (arcmin):", className="form-label small"),
                                    dbc.Input(
                                        id="sidebar-cutout-size",
                                        type="number",
                                        value=5.0,
                                        min=1.0,
                                        max=20.0,
                                        step=0.5,
                                        size="sm"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Type:", className="form-label small"),
                                    dbc.Select(
                                        id="sidebar-cutout-type",
                                        options=[
                                            {"label": "Density", "value": "density"},
                                            {"label": "Sky", "value": "sky"},
                                            {"label": "Both", "value": "both"}
                                        ],
                                        value="density",
                                        size="sm"
                                    )
                                ], width=6)
                            ], className="mb-2"),
                            dbc.Button(
                                "Generate Cutout",
                                id="sidebar-generate-cutout",
                                color="primary",
                                size="sm",
                                className="w-100",
                                n_clicks=0
                            )
                        ], id="sidebar-cutout-options", is_open=False)
                    ])
                ])
            ], id="cluster-analysis-panel", is_open=False, className="mb-3"),
            
            # Instruction text when no cluster selected
            html.Div([
                html.P([
                    html.I(className="fas fa-mouse-pointer me-2"),
                    "Click any cluster point to analyze"
                ], className="text-muted small text-center mb-0")
            ], id="cluster-instruction-text")
            
        ], className="mb-4")
