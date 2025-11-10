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
                # Left sidebar with controls - Enhanced beautiful design
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.Div([
                                html.I(className="fas fa-sliders-h me-2 text-white"),
                                html.H5("Visualization Controls", className="mb-0 d-inline-block text-white"),
                            ], className="d-flex align-items-center justify-content-center")
                        ], className="bg-gradient text-white", style={
                            'background': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                            'border-radius': '15px 15px 0 0'
                        }),
                        dbc.CardBody([
                            # Header info with beautiful styling
                            dbc.Alert([
                                html.I(className="fas fa-info-circle me-2"),
                                "Options update in real-time while preserving zoom level"
                            ], color="info", className="mb-3 small text-center border-0 card-hover", style={
                                'background': 'linear-gradient(45deg, #e3f2fd, #f3e5f5)',
                                'border-radius': '10px',
                                'box-shadow': '0 2px 10px rgba(0,0,0,0.1)'
                            }),
                            
                            # Main render button with enhanced styling
                            AppLayout._create_main_render_section(),

                            # Elegant divider
                            html.Div(className="position-relative my-4", children=[
                                html.Hr(className="border-primary", style={'border-width': '2px'}),
                                html.Div("⚙️", className="position-absolute top-50 start-50 translate-middle bg-white px-2 text-primary", style={'font-size': '1.2rem'})
                            ]),

                            # Collapsible sections for better organization
                            AppLayout._create_collapsible_sections(),
                            
                        ], style={'overflow-y': 'auto', 'max-height': 'calc(100vh - 200px)'})
                    ], className="h-100 shadow-lg border-0 sidebar-card card-hover", style={
                        'background': 'linear-gradient(180deg, #ffffff 0%, #f8f9ff 100%)',
                        'border-radius': '15px'
                    })
                ], width=2, className="pe-3"),
                
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
        """Create algorithm selection section with enhanced styling"""
        return html.Div([
            html.Div([
                html.I(className="fas fa-cogs me-2 text-primary"),
                html.Label("Algorithm Selection:", className="fw-bold mb-0")
            ], className="d-flex align-items-center mb-3"),
            
            dbc.Card([
                dbc.CardBody([
                    dcc.Dropdown(
                        id='algorithm-dropdown',
                        options=[
                            {'label': 'PZWAV', 'value': 'PZWAV'},
                            {'label': 'AMICO', 'value': 'AMICO'},
                            {'label': '🌌 PZWAV & AMICO', 'value': 'BOTH'}
                        ],
                        value='PZWAV',
                        clearable=False,
                        style={
                            'border-radius': '8px',
                            'font-weight': '500'
                        }
                    )
                ], className="p-2")
            ], className="border-0 shadow-sm mb-3", style={
                'background': 'linear-gradient(45deg, #f8f9ff, #ffffff)',
                'border-radius': '10px'
            })
        ])
    

    @staticmethod
    def _create_merged_clusters_section():
        return html.Div([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-layer-group me-0 text-primary"),
                        dbc.Switch(
                            id="merged-clusters-switch",
                            label="Show merged catalog members",
                            value=False,
                            className="ms-0"
                        )
                    ], className="d-flex align-items-left mb-0"),
                    html.Small([
                        html.I(className="fas fa-info-circle me-0"),
                        "Cluster detections from Merge_Cl code, merged over Cluster-Tiles"
                    ], className="text-muted ms-0")
                ])
            ], className="mb-3 border-0 shadow-sm", style={
                'background': 'linear-gradient(45deg, #f0f8ff, #ffffff)',
                'border-radius': '10px'
            })
        ])
    
    @staticmethod
    def _create_cluster_matching_section():
        """Create cluster matching section with enhanced styling"""
        return html.Div([
            # Enhanced switch options with beautiful cards
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-object-group me-0 text-primary"),
                        dbc.Switch(
                            id="matching-clusters-switch",
                            label="Show matched clusters (CAT-CL)",
                            value=False,
                            disabled=True,
                            className="ms-0"
                        )
                    ], className="d-flex align-items-left mb-0"),
                    html.Small([
                        html.I(className="fas fa-info-circle me-0"),
                        "Only in PZWAV+AMICO mode"
                    ], className="text-muted ms-0")
                ])
            ], className="mb-3 border-0 shadow-sm", style={
                'background': 'linear-gradient(45deg, #f0f8ff, #ffffff)',
                'border-radius': '10px'
            })
        ])
    
    @staticmethod
    def _create_snr_section():
        """Create SNR filtering section with enhanced styling"""

        snr_pzwav_tab = dbc.Card([
            dbc.CardBody([
                # Range display with beautiful styling
                dbc.Badge(
                    id="snr-range-display-pzwav",
                    color="light",
                    className="w-100 mb-3 p-2 fs-6 badge-enhanced status-indicator",
                    style={
                        'background': 'linear-gradient(45deg, #e8f5e8, #f0f8f0)',
                        'color': '#2d5a2d',
                        'border-radius': '8px',
                        'border': '1px solid rgba(46, 204, 113, 0.3)'
                    }
                ),
                
                # Enhanced range slider
                html.Div([
                    dcc.RangeSlider(
                        id='snr-range-slider-pzwav',
                        min=0,
                        max=100,
                        step=0.1,
                        marks={},
                        value=[0, 100],
                        tooltip={
                            "placement": "bottom", 
                            "always_visible": False,
                            "style": {"fontSize": "12px"}
                        },
                        allowCross=False,
                        className="custom-range-slider"
                    )
                ], className="mb-1", style={
                    'padding': '10px 15px', 
                    'margin': '5px 0',
                    'minHeight': '60px'
                }),
                
                # Enhanced apply button
                dbc.Button([
                    html.I(className="fas fa-filter me-2"),
                    "Apply SNR Filter (PZWAV)"
                ],
                    id="snr-render-button-pzwav",
                    color="success",
                    size="sm",
                    className="w-100 shadow-sm btn-enhanced",
                    n_clicks=0,
                    disabled=True,
                    style={
                        'border-radius': '8px',
                        'font-weight': '600'
                    }
                )
            ], className="p-3")
        ], className="border-0 shadow-sm mb-3", style={
            'background': 'linear-gradient(135deg, #f0fff0, #ffffff)',
            'border-radius': '12px'
        })

        snr_amico_tab = dbc.Card([
            dbc.CardBody([
                # Range display with beautiful styling
                dbc.Badge(
                    id="snr-range-display-amico",
                    color="light",
                    className="w-100 mb-3 p-2 fs-6 badge-enhanced status-indicator",
                    style={
                        'background': 'linear-gradient(45deg, #e8f5e8, #f0f8f0)',
                        'color': '#2d5a2d',
                        'border-radius': '8px',
                        'border': '1px solid rgba(46, 204, 113, 0.3)'
                    }
                ),
                
                # Enhanced range slider
                html.Div([
                    dcc.RangeSlider(
                        id='snr-range-slider-amico',
                        min=0,
                        max=100,
                        step=0.1,
                        marks={},
                        value=[0, 100],
                        tooltip={
                            "placement": "bottom", 
                            "always_visible": False,
                            "style": {"fontSize": "12px"}
                        },
                        allowCross=False,
                        className="custom-range-slider"
                    )
                ], className="mb-1", style={
                    'padding': '10px 15px', 
                    'margin': '5px 0',
                    'minHeight': '60px'
                }),
                
                # Enhanced apply button
                dbc.Button([
                    html.I(className="fas fa-filter me-2"),
                    "Apply SNR Filter (AMICO)"
                ],
                    id="snr-render-button-amico",
                    color="success",
                    size="sm",
                    className="w-100 shadow-sm btn-enhanced",
                    n_clicks=0,
                    disabled=True,
                    style={
                        'border-radius': '8px',
                        'font-weight': '600'
                    }
                )
            ], className="p-3")
        ], className="border-0 shadow-sm mb-3", style={
            'background': 'linear-gradient(135deg, #f0fff0, #ffffff)',
            'border-radius': '12px'
        })

        return html.Div([
            html.Div([
                html.I(className="fas fa-signal me-1 text-success"),
                html.Label("SNR Filtering:", className="fw-bold mb-1")
            ], className="d-flex align-items-left mb-0"),
            
            dbc.Tabs([
                dbc.Tab(label="PZWAV", children=[snr_pzwav_tab]),
                dbc.Tab(label="AMICO", children=[snr_amico_tab])
            ])
        ])
    
    @staticmethod
    def _create_redshift_section():
        """Create redshift filtering section with enhanced styling"""
        return html.Div([
            html.Div([
                html.I(className="fas fa-expand-arrows-alt me-1 text-danger"),
                html.Label("Redshift Filtering:", className="fw-bold mb-1")
            ], className="d-flex align-items-left mb-0"),
            
            dbc.Card([
                dbc.CardBody([
                    # Range display with beautiful styling  
                    dbc.Badge(
                        id="redshift-range-display",
                        color="light", 
                        className="w-100 mb-3 p-2 fs-6 badge-enhanced status-indicator",
                        style={
                            'background': 'linear-gradient(45deg, #ffe8e8, #fff0f0)',
                            'color': '#5a2d2d',
                            'border-radius': '8px',
                            'border': '1px solid rgba(231, 76, 60, 0.3)'
                        }
                    ),
                    
                    # Enhanced range slider
                    html.Div([
                        dcc.RangeSlider(
                            id='redshift-range-slider',
                            min=0,
                            max=10,
                            step=0.1,
                            marks={},
                            value=[0, 10],
                            tooltip={
                                "placement": "bottom", 
                                "always_visible": False,
                                "style": {"fontSize": "12px"}
                            },
                            allowCross=False,
                            className="custom-range-slider"
                        )
                    ], className="mb-1", style={
                        'padding': '10px 15px', 
                        'margin': '5px 0',
                        'minHeight': '60px'
                    }),
                    
                    # Enhanced apply button
                    dbc.Button([
                        html.I(className="fas fa-filter me-2"),
                        "Apply Redshift Filter"
                    ],
                        id="redshift-render-button",
                        color="danger", 
                        size="sm",
                        className="w-100 shadow-sm btn-enhanced",
                        n_clicks=0,
                        disabled=True,
                        style={
                            'border-radius': '8px',
                            'font-weight': '600'
                        }
                    )
                ], className="p-3")
            ], className="border-0 shadow-sm", style={
                'background': 'linear-gradient(135deg, #fff0f0, #ffffff)',
                'border-radius': '12px'
            })
        ])
    
    @staticmethod
    def _create_display_options_section():
        """Create display options section with enhanced styling"""
        return html.Div([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-shapes me-0 text-info"),
                        dbc.Switch(
                            id="polygon-switch", 
                            label="Fill CL-tiles (CORE) polygons",
                            value=False,
                            className="ms-0"
                        )
                    ], className="d-flex align-items-left mb-1")
                ])
            ], className="mb-3 border-0 shadow-sm", style={
                'background': 'linear-gradient(45deg, #e8f8f8, #ffffff)',
                'border-radius': '10px'
            }),
            
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-th me-0 text-warning"),
                        dbc.Switch(
                            id="mer-switch",
                            label="Show MER tiles (up to LEV2 in CL-tiles)",
                            value=True,
                            className="ms-0"
                        )
                    ], className="d-flex align-items-left mb-1"),
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        "Only with open cluster-tile polygons"
                    ], className="text-muted ms-0")
                ])
            ], className="mb-3 border-0 shadow-sm", style={
                'background': 'linear-gradient(45deg, #fff8e1, #ffffff)',
                'border-radius': '10px'
            }),
            
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-expand me-0 text-success"),
                        dbc.Switch(
                            id="aspect-ratio-switch",
                            label="Free aspect ratio",
                            value=True,
                            className="ms-0"
                        )
                    ], className="d-flex align-items-left mb-1"),
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        "Default: maintain astronomical aspect"
                    ], className="text-muted ms-0")
                ])
            ], className="border-0 shadow-sm", style={
                'background': 'linear-gradient(45deg, #e8f5e8, #ffffff)',
                'border-radius': '10px'
            })
        ])
    
    @staticmethod
    def _create_catred_data_section():
        """Create High-res CATRED data section with enhanced styling"""
        return html.Div([
            # Main CATRED toggle with beautiful styling
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-microscope me-0 text-warning"),
                        dbc.Switch(
                            id="catred-mode-switch",
                            label="Masked CATRED data",
                            value=True,
                            className="ms-1"
                        )
                    ], className="d-flex align-items-center mb-0"),
                    dbc.Badge([
                        html.I(className="fas fa-zoom-in me-1"),
                        "When zoomed < 2°"
                    ], color="warning", className="opacity-75")
                ])
            ], className="mb-3 border-0 shadow-sm", style={
                'background': 'linear-gradient(45deg, #fff3cd, #ffffff)',
                'border-radius': '12px'
            }),
            
            # Threshold controls in beautiful card
            dbc.Card([
                dbc.CardHeader([
                    html.Div([
                        html.I(className="fas fa-sliders-h me-0"),
                        html.H6("Coverage Threshold", className="mb-0")
                    ], className="d-flex align-items-center")
                ], className="border-0", style={
                    'background': 'linear-gradient(45deg, #ffeaa7, #fdcb6e)',
                    'border-radius': '8px 8px 0 0'
                }),
                dbc.CardBody([
                    html.Div([
                        dcc.Slider(
                            id="catred-threshold-slider",
                            min=0.0,
                            max=1.0,
                            step=0.01,
                            value=0.8,
                            marks={
                                0.0: {"label": "0.0", "style": {"color": "#666", "fontSize": "12px"}},
                                0.2: {"label": "0.2", "style": {"color": "#666", "fontSize": "12px"}},
                                0.4: {"label": "0.4", "style": {"color": "#666", "fontSize": "12px"}},
                                0.6: {"label": "0.6", "style": {"color": "#666", "fontSize": "12px"}},
                                0.8: {"label": "0.8", "style": {"color": "#e17055", "font-weight": "bold", "fontSize": "13px"}},
                                1.0: {"label": "1.0", "style": {"color": "#666", "fontSize": "12px"}}
                            },
                            tooltip={
                                "placement": "bottom", 
                                "always_visible": False,
                                "style": {"fontSize": "12px"}
                            },
                            className="custom-slider"
                        )
                    ], id="catred-threshold-container", className="mb-0", 
                       style={
                           'padding': '10px 15px', 
                           'margin': '5px 0',
                           'minHeight': '60px'
                       }),
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        "For masked CATRED filtering"
                    ], className="text-muted")
                ])
            ], className="mb-3 border-0 shadow-sm", style={'border-radius': '12px'}),
            
            # Magnitude controls in beautiful card
            dbc.Card([
                dbc.CardHeader([
                    html.Div([
                        html.I(className="fas fa-star me-2"),
                        html.H6("Magnitude Limit (H-band)", className="mb-0")
                    ], className="d-flex align-items-center")
                ], className="border-0", style={
                    'background': 'linear-gradient(45deg, #a29bfe, #6c5ce7)',
                    'color': 'white',
                    'border-radius': '8px 8px 0 0'
                }),
                dbc.CardBody([
                    html.Div([
                        dcc.Slider(
                            id="magnitude-limit-slider",
                            min=20.0,
                            max=32.0,
                            step=0.1,
                            value=24.0,
                            marks={
                                20.0: {"label": "20.0", "style": {"color": "#666", "fontSize": "12px"}},
                                22.0: {"label": "22.0", "style": {"color": "#666", "fontSize": "12px"}},
                                24.0: {"label": "24.0", "style": {"color": "#6c5ce7", "font-weight": "bold", "fontSize": "13px"}},
                                26.0: {"label": "26.0", "style": {"color": "#666", "fontSize": "12px"}},
                                28.0: {"label": "28.0", "style": {"color": "#666", "fontSize": "12px"}},
                                30.0: {"label": "30.0", "style": {"color": "#666", "fontSize": "12px"}},
                                32.0: {"label": "32.0", "style": {"color": "#666", "fontSize": "12px"}}
                            },
                            tooltip={
                                "placement": "bottom", 
                                "always_visible": False,
                                "style": {"fontSize": "12px"}
                            },
                            className="custom-slider"
                        )
                    ], id="magnitude-limit-container", className="mb-0", 
                       style={
                           'padding': '10px 15px', 
                           'margin': '5px 0',
                           'minHeight': '60px'
                       }),
                    html.Small([
                        html.I(className="fas fa-info-circle me-1"),
                        "Keep sources brighter than limit"
                    ], className="text-muted")
                ])
            ], className="mb-3 border-0 shadow-sm", style={'border-radius': '12px'}),
            
            # CATRED Data Controls with enhanced styling
            dbc.Card([
                dbc.CardHeader([
                    html.Div([
                        html.I(className="fas fa-tools me-0"),
                        html.H6("CATRED Data Controls", className="mb-0")
                    ], className="d-flex align-items-center")
                ], className="border-0", style={
                    'background': 'linear-gradient(45deg, #74b9ff, #0984e3)',
                    'color': 'white',
                    'border-radius': '8px 8px 0 0'
                }),
                dbc.CardBody([
                    # Render button
                    dbc.Button([
                        html.I(className="fas fa-eye me-2"),
                        "🔍 Render CATRED Data"
                    ],
                        id="catred-render-button",
                        color="info",
                        size="sm", 
                        className="w-100 mb-0 shadow-sm btn-enhanced",
                        n_clicks=0,
                        disabled=True,
                        style={
                            'border-radius': '8px',
                            'font-weight': '600'
                        }
                    ),
                    html.Small([
                        html.I(className="fas fa-search-plus me-0"),
                        "Zoom in first, then click"
                    ], className="text-muted d-block text-left mb-3"),
                    
                    # Clear button
                    dbc.Button([
                        html.I(className="fas fa-trash-alt me-2"), 
                        "🗑️ Clear All CATRED Data"
                    ],
                        id="catred-clear-button",
                        color="warning",
                        size="sm",
                        className="w-100 shadow-sm btn-enhanced",
                        n_clicks=0,
                        style={
                            'border-radius': '8px',
                            'font-weight': '600'
                        }
                    ),
                    html.Small([
                        html.I(className="fas fa-eraser me-1"),
                        "Remove all CATRED traces"
                    ], className="text-muted d-block text-center")
                ], className="p-3")
            ], id="catred-controls-container", className="border-0 shadow-sm", style={'border-radius': '12px'})
        ])
    
    @staticmethod
    def _create_mosaic_controls_section():
        """Create mosaic image controls section with enhanced styling"""
        return html.Div([
            # Main mosaic toggle
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-images me-0 text-info"),
                        dbc.Switch(
                            id="mosaic-enable-switch",
                            label="Enable mosaic images",
                            value=True,
                            disabled=False,
                            className="ms-1"
                        )
                    ], className="d-flex align-items-left mb-0"),
                ])
            ], className="mb-3 border-0 shadow-sm", style={
                'background': 'linear-gradient(45deg, #e8f4f8, #ffffff)',
                'border-radius': '10px'
            }),
            
            # Opacity control
            dbc.Card([
                dbc.CardHeader([
                    html.Div([
                        html.I(className="fas fa-adjust me-2"),
                        html.H6("Mosaic Opacity", className="mb-0")
                    ], className="d-flex align-items-center")
                ], className="border-0", style={
                    'background': 'linear-gradient(45deg, #74b9ff, #0984e3)',
                    'color': 'white',
                    'border-radius': '8px 8px 0 0'
                }),
                dbc.CardBody([
                    html.Div([
                        dcc.Slider(
                            id="mosaic-opacity-slider",
                            min=0.1,
                            max=1.0,
                            step=0.1,
                            value=0.7,
                            marks={
                                0.1: {"label": '10%', "style": {"color": "#666", "fontSize": "12px"}},
                                0.5: {"label": '50%', "style": {"color": "#0984e3", "font-weight": "bold", "fontSize": "13px"}},
                                1.0: {"label": '100%', "style": {"color": "#666", "fontSize": "12px"}}
                            },
                            tooltip={
                                "placement": "bottom", 
                                "always_visible": False,
                                "style": {"fontSize": "12px"}
                            },
                            disabled=False,
                            className="custom-slider"
                        )
                    ], style={
                        'padding': '5px 10px', 
                        'margin': '0',
                        'minHeight': '50px'
                    })
                ], className="p-2")
            ], className="mb-1 border-0 shadow-sm", style={'border-radius': '12px'}),
            
            # Load mosaic button
            dbc.Card([
                dbc.CardBody([
                    dbc.Button([
                        html.I(className="fas fa-download me-2"),
                        "🖼️ Load Mosaic in Zoom"
                    ],
                        id="mosaic-render-button",
                        color="info",
                        size="sm",
                        className="w-100 mb-2 shadow-sm btn-enhanced",
                        n_clicks=0,
                        disabled=True,
                        style={
                            'border-radius': '8px',
                            'font-weight': '600'
                        }
                    ),
                    html.Small([
                        html.I(className="fas fa-image me-1"),
                        "Load mosaic images for visible MER tiles"
                    ], className="text-muted d-block text-left mb-0")
                ], className="p-3")
            ], className="mb-3 border-0 shadow-sm", style={
                'background': 'linear-gradient(45deg, #e8f4f8, #ffffff)',
                'border-radius': '12px'
            }),

            dbc.Card([
                dbc.CardHeader([
                    html.Div([
                        html.I(className="fas fa-adjust me-2"),
                        html.H6("Mask Opacity", className="mb-0")
                    ], className="d-flex align-items-center")
                ], className="border-0", style={
                    'background': 'linear-gradient(45deg, #74b9ff, #0984e3)',
                    'color': 'white',
                    'border-radius': '8px 8px 0 0'
                }),
                dbc.CardBody([
                    html.Div([
                        dcc.Slider(
                            id="mask-opacity-slider",
                            min=0.1,
                            max=1.0,
                            step=0.1,
                            value=0.4,
                            marks={
                                0.1: {"label": '10%', "style": {"color": "#666", "fontSize": "12px"}},
                                0.5: {"label": '50%', "style": {"color": "#0984e3", "font-weight": "bold", "fontSize": "13px"}},
                                1.0: {"label": '100%', "style": {"color": "#666", "fontSize": "12px"}}
                            },
                            tooltip={
                                "placement": "bottom", 
                                "always_visible": False,
                                "style": {"fontSize": "12px"}
                            },
                            disabled=False,
                            className="custom-slider"
                        )
                    ], style={
                        'padding': '5px 10px', 
                        'margin': '0',
                        'minHeight': '50px'
                    })
                ], className="p-2")
            ], className="mb-1 border-0 shadow-sm", style={'border-radius': '12px'}),
            
            dbc.Card([
                dbc.CardBody([
                    dbc.Button([
                        html.I(className="fas fa-download me-2"),
                        "🖼️ Healpix Mask in Zoom"
                    ],
                        id="healpix-mask-button",
                        color="info",
                        size="sm",
                        className="w-100 mb-2 shadow-sm btn-enhanced",
                        n_clicks=0,
                        disabled=True,
                        style={
                            'border-radius': '8px',
                            'font-weight': '600'
                        }
                    ),
                    html.Small([
                        html.I(className="fas fa-image me-1"),
                        "Load healpix mask overlay for visible MER tiles"
                    ], className="text-muted d-block text-left mb-0")
                ], className="p-3")
            ], className="mb-3 border-0 shadow-sm", style={
                'background': 'linear-gradient(45deg, #e8f4f8, #ffffff)',
                'border-radius': '12px'
            }),

        ])
    
    @staticmethod
    def _create_main_render_section():
        """Create main render button section with beautiful styling"""
        return dbc.Card([
            dbc.CardBody([
                dbc.Button([
                    html.I(className="fas fa-rocket me-2"),
                    "🚀 Initial Render"
                ],
                    id="render-button",
                    color="primary",
                    size="lg",
                    className="w-100 mb-2 shadow-sm btn-enhanced pulse",
                    n_clicks=0,
                    style={
                        'background': 'linear-gradient(45deg, #007bff, #0056b3)',
                        'border': 'none',
                        'border-radius': '12px',
                        'font-weight': 'bold',
                        'text-transform': 'uppercase',
                        'letter-spacing': '0.5px',
                        'box-shadow': '0 4px 15px rgba(0,123,255,0.3)'
                    }
                ),
                html.Small([
                    html.I(className="fas fa-magic me-1"),
                    "After initial render, options update automatically"
                ], className="text-muted d-block text-center fst-italic")
            ], className="p-2")
        ], className="mb-3 border-0 card-hover", style={
            'background': 'linear-gradient(135deg, #e8f4f8, #f0f8ff)',
            'border-radius': '12px',
            'box-shadow': '0 2px 10px rgba(0,0,0,0.1)'
        })

    @staticmethod
    def _create_collapsible_sections():
        """Create organized collapsible sections for better UX"""
        return html.Div([
            # Core Settings Section
            AppLayout._create_collapsible_card(
                "🎯 Detected Clusters",
                "clusters-settings",
                [
                    AppLayout._create_algorithm_section(),
                    AppLayout._create_merged_clusters_section(),
                    AppLayout._create_cluster_matching_section(),
                    AppLayout._create_snr_section(),
                    AppLayout._create_redshift_section(),
                ],
                is_open=False,
                color="primary"
            ),
            
            # Advanced Data Section
            AppLayout._create_collapsible_card(
                "🔬 CatRed Sources",
                "catred-data", 
                [AppLayout._create_catred_data_section()],
                is_open=False,
                color="warning"
            ),
            
            # Image Controls Section
            AppLayout._create_collapsible_card(
                "🖼️ Mosaic / Healpix Mask",
                "image-controls",
                [AppLayout._create_mosaic_controls_section()],
                is_open=False,
                color="info"
            ),

            # Display Options Section  
            AppLayout._create_collapsible_card(
                "🎨 Display Options",
                "display-options",
                [AppLayout._create_display_options_section()],
                is_open=False,
                color="success"
            )
        ])

    @staticmethod
    def _create_collapsible_card(title, card_id, content, is_open=True, color="primary"):
        """Create a beautiful collapsible card section"""
        return dbc.Card([
            dbc.CardHeader([
                dbc.Button([
                    html.I(className=f"fas fa-chevron-{'down' if is_open else 'right'} me-2"),
                    title
                ],
                    id=f"{card_id}-toggle",
                    color="link",
                    className="text-decoration-none fw-bold w-100 text-start p-2 collapse-header",
                    style={'color': f'var(--bs-{color})'}
                )
            ], className="border-0 p-0", style={
                'background': f'linear-gradient(45deg, var(--bs-{color}-100), var(--bs-{color}-50))',
                'border-radius': '8px 8px 0 0'
            }),
            dbc.Collapse([
                dbc.CardBody(content, className="pt-3")
            ], id=f"{card_id}-collapse", is_open=is_open)
        ], className="mb-3 border-0 shadow-sm card-hover", style={
            'border-radius': '12px',
            'box-shadow': '0 4px 15px rgba(0,0,0,0.1)'
        })
    
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
                        html.Small("Create MER mosaic cutout around this cluster", className="text-muted")
                    ], width=6),
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-magnifying-glass me-2"), "View CATRED Box"],
                            id="cluster-catred-box-button",
                            color="success", 
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("View CATRED Box", className="text-muted")
                    ], width=6),
                ], className="mb-3"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-layer-group me-2"), "Healpix Mask Cutout"],
                            id="cluster-healpix-mask-button", 
                            color="info",
                            disabled=True,
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("Coming soon ...", className="text-muted")
                    ], width=6),
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-table me-2"), "Export Data"],
                            id="cluster-export-button",
                            color="warning",
                            disabled=True,
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
                                            {"label": "MER Mosaic", "value": "mermosaic"},
                                            {"label": "Density Map", "value": "density"},
                                            {"label": "Both", "value": "both"}
                                        ],
                                        value="mermosaic",
                                        className="mb-2"
                                    )
                                ], width=6)
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Opacity:", className="form-label"),
                                    dbc.Input(
                                        id="cutout-opacity-input",
                                        type="number",
                                        value=1.0,
                                        min=0.0,
                                        max=1.0,
                                        step=0.1,
                                        className="mb-2"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Colorscale:", className="form-label"),
                                    dbc.Select(
                                        id="cutout-colorscale",
                                        options=[
                                            {"label": "viridis", "value": "viridis"},
                                            {"label": "gray", "value": "gray"},
                                            {"label": "plasma", "value": "plasma"}
                                        ],
                                        value="viridis",
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
                ], id="cutout-options-collapse", is_open=False),

                # CATRED data box options (initially hidden)
                dbc.Collapse([
                    dbc.Card([
                        dbc.CardHeader("CATRED Data Box Options"),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Box Size (arcmin):", className="form-label"),
                                    dbc.Input(
                                        id="catred-box-size-input",
                                        type="number",
                                        value=10.0,
                                        min=5.0,
                                        max=50.0,
                                        step=1.0,
                                        className="mb-2"
                                    )
                                ], width=6)
                            ]),
                            dbc.Button(
                                "Generate CATRED Data Box",
                                id="view-catred-box-button",
                                color="success",
                                className="w-100",
                                n_clicks=0
                            )
                        ])
                    ])
                ], id="catred-box-options-collapse", is_open=False)
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
                            disabled=False,
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        # html.Small("Click to see options", className="text-muted d-block text-center")
                        html.Small("Click to see options", className="text-muted d-block text-center")
                    ], width=6),

                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-magnifying-glass me-2"), "CATRED data box"],
                            id="tab-catred-box-button",
                            color="success",
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("CATRED data in selected box", className="text-muted d-block text-center")
                    ], width=6),
                ], className="mb-3"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-layer-group me-2"), "Healpix Mask Cutout"],
                            id="tab-mask-cutout-button",
                            color="info",
                            disabled=False,
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("Click to see options", className="text-muted d-block text-center")
                    ], width=6),

                    dbc.Col([
                        dbc.Button(
                            [html.I(className="fas fa-download me-2"), "Export Data"],
                            id="tab-export-button",
                            color="warning",
                            disabled=True,
                            className="w-100 mb-2",
                            n_clicks=0
                        ),
                        html.Small("Coming soon ...", className="text-muted d-block text-center")
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
                                        value=2.0,
                                        min=0.0,
                                        max=20.0,
                                        step=1.0,
                                        className="mb-2"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Data Type:", className="form-label"),
                                    dbc.Select(
                                        id="tab-cutout-type",
                                        options=[
                                            {"label": "MER Mosaic", "value": "mermosaic"},
                                            # {"label": "Density Map", "value": "density"},
                                            # {"label": "Both", "value": "both"}
                                        ],
                                        value="mermosaic",
                                        className="mb-2"
                                    )
                                ], width=6)
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Opacity (0 to 1):", className="form-label"),
                                    dbc.Input(
                                        id="tab-cutout-opacity",
                                        type="number",
                                        value=1.0,
                                        min=0.0,
                                        max=1.0,
                                        step=0.1,
                                        className="mb-2"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Colorscale:", className="form-label"),
                                    dbc.Select(
                                        id="tab-cutout-colorscale",
                                        options=[
                                            {"label": "viridis", "value": "viridis"},
                                            {"label": "gray", "value": "gray"},
                                            {"label": "plasma", "value": "plasma"}
                                        ],
                                        value="viridis",
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

                # CATRED box options (expandable)
                dbc.Collapse([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H6([
                                html.I(className="fas fa-cog me-2"),
                                "CATRED Box Options"
                            ], className="mb-0")
                        ]),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Box Size (arcmin):", className="form-label"),
                                    dbc.Input(
                                        id="tab-catred-box-size",
                                        type="number",
                                        value=2.0,
                                        min=1.0,
                                        max=10.0,
                                        step=1.0,
                                        className="mb-2"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Redshift bin width:", className="form-label"),
                                    dbc.Input(
                                        id="tab-catred-redshift-bin-width",
                                        type="number",
                                        value=0.5,
                                        min=0,
                                        max=3.0,
                                        step=0.1,
                                        className="mb-2"
                                    )
                                ], width=6)
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Mask Threshold:", className="form-label"),
                                    dbc.Input(
                                        id="tab-catred-mask-threshold",
                                        type="number",
                                        value=0.8,
                                        min=0.0,
                                        max=1.0,
                                        step=0.1,
                                        className="mb-2"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Magnitude Limit:", className="form-label"),
                                    dbc.Input(
                                        id="tab-catred-maglim",
                                        type="number",
                                        value=24.0,
                                        min=20.0,
                                        max=32.0,
                                        step=1.0,
                                        className="mb-2"
                                    )
                                ], width=6)
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Marker Size:", className="form-label"),
                                    dbc.Select(
                                        id="tab-catred-marker-size",
                                        options=[
                                            {"label": "Constant size", "value": "set_size_custom"},
                                            {"label": "KRON Radius", "value": "set_size_kronradius"},
                                            # {"label": "Both", "value": "both"}
                                        ],
                                        value="set_size_custom",
                                        className="mb-2"
                                    )
                                ], width=4),
                                dbc.Col([
                                    html.Label("Custom Size:", className="form-label"),
                                    dbc.Input(
                                        id="tab-catred-marker-size-custom",
                                        type="number",
                                        value=10.0,
                                        min=5.0,
                                        max=50.0,
                                        step=5.0,
                                        className="mb-2"
                                    )
                                ], width=4),
                                dbc.Col([
                                    html.Label("Marker Color:", className="form-label"),
                                    dbc.Input(
                                        id="tab-catred-marker-color-picker",
                                        type="color",
                                        value="#00FFF2",
                                        className="w-100",
                                        style={'height': '38px', 'cursor': 'pointer', 'border-radius': '6px'}
                                    )
                                ], width=4)
                            ]),
                            dbc.Button(
                                [html.I(className="fas fa-play me-2"), "View CATRED Box"],
                                id="tab-view-catred-box",
                                color="success",
                                className="w-100",
                                n_clicks=0
                            )
                        ])
                    ])
                ], id="tab-catred-box-options", is_open=False, className="mb-3"),

                # Mask cutout options (expandable)
                dbc.Collapse([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H6([
                                html.I(className="fas fa-cog me-2"),
                                "Healpix Mask Cutout Options"
                            ], className="mb-0")
                        ]),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Size (arcmin):", className="form-label"),
                                    dbc.Input(
                                        id="tab-mask-cutout-size",
                                        type="number",
                                        value=2.0,
                                        min=0.0,
                                        max=20.0,
                                        step=1.0,
                                        className="mb-2"
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Opacity (0 to 1):", className="form-label"),
                                    dbc.Input(
                                        id="tab-mask-cutout-opacity",
                                        type="number",
                                        value=0.3,
                                        min=0.0,
                                        max=1.0,
                                        step=0.1,
                                        className="mb-2"
                                    )
                                ], width=6)
                            ]),
                            dbc.Button(
                                [html.I(className="fas fa-play me-2"), "Generate Mask Cutout"],
                                id="tab-generate-mask-cutout",
                                color="primary",
                                className="w-100",
                                n_clicks=0
                            )
                        ])
                    ])
                ], id="tab-mask-cutout-options", is_open=False, className="mb-3"),
                
                # Analysis results area
                html.Div([
                    html.H6("📊 Analysis Results", className="mb-2"),
                    html.Div(id="cluster-analysis-results", children=[
                        html.P("Analysis results will appear here", className="text-muted small")
                    ])
                ])
                
            ], id="cluster-selected-content", style={'display': 'none'})
            
        ], style={'height': '60vh', 'overflow-y': 'auto'})
