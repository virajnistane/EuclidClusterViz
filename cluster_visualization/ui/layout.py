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
                            
                            # Algorithm selection
                            AppLayout._create_algorithm_section(),
                            
                            # SNR Filtering section
                            AppLayout._create_snr_section(),
                            
                            # Display options
                            AppLayout._create_display_options_section(),
                            
                            # MER Data controls
                            AppLayout._create_mer_controls_section(),
                            
                            html.Hr(),
                            
                            # Main render button
                            AppLayout._create_main_render_section()
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
                        
                        # PHZ_PDF plot
                        dbc.Col([
                            dcc.Loading(
                                id="loading-phz",
                                children=[
                                    dcc.Graph(
                                        id='phz-pdf-plot',
                                        style={'height': '75vh', 'width': '100%', 'min-height': '500px'},
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
                        ], width=4)
                    ]),
                    
                    # Status info row
                    dbc.Row([
                        dbc.Col([
                            html.Div(id="status-info", className="mt-2")
                        ])
                    ])
                ], width=10)
            ], className="g-0")  # Remove gutters for tighter layout
            
        ], fluid=True, className="px-3")
    
    @staticmethod
    def _create_algorithm_section():
        """Create algorithm selection section"""
        return html.Div([
            html.Label("Algorithm:", className="fw-bold mb-2"),
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
            html.Label("SNR Filtering:", className="fw-bold mb-2"),
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
    def _create_display_options_section():
        """Create display options section"""
        return html.Div([
            html.Label("Display Options:", className="fw-bold mb-2"),
            
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
            
            html.Div([
                html.Label("High-res CATRED data:", className="fw-bold mb-2"),
                dbc.RadioItems(
                    id="catred-mode-radio",
                    options=[
                        {"label": "No CATRED data", "value": "none"},
                        {"label": "Unmasked CATRED data", "value": "unmasked"},
                        {"label": "Masked CATRED data", "value": "masked"},
                    ],
                    value="masked",
                    inline=True,
                ),
                html.Small("(When zoomed < 2°)", className="text-muted")
            ], className="mb-3"),
            
            # Threshold slider for masked CATRED data
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
            ], className="mb-3"),
        ], className="mb-4")
    
    @staticmethod
    def _create_mer_controls_section():
        """Create MER data controls section"""
        return html.Div([
            html.Label("CATRED Data Controls:", className="fw-bold mb-2"),
            
            html.Div([
                dbc.Button(
                    "🔍 Render CATRED Data",
                    id="mer-render-button",
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
                    id="mer-clear-button",
                    color="warning",
                    size="sm",
                    className="w-100 mb-2",
                    n_clicks=0
                ),
                html.Small("(Remove all CATRED traces)", className="text-muted d-block text-center")
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
