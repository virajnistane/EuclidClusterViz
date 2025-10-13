#!/usr/bin/env python3
"""
Cluster Visualization Dash App

A self-contained Dash application for interactive cluster detection data visualization.
This app runs as a web server and automatically opens in browser without manual intervention.

Features:
- Algorithm switching (PZWAV/AMICO)
- Manual render control with interactive button
- Always-visible polygon outlines with fill toggle
- MER tile display (only available with outline polygons for better visibility)
- Configurable aspect ratio: free (flexible zoom, default) or equal (astronomical accuracy)
- Responsive plot sizing with 1200x900 dimensions

REQUIREMENTS:
- Must activate EDEN environment first: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
- This provides required packages: astropy, plotly, pandas, numpy, shapely, dash
"""

import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from astropy.io import fits
from shapely.geometry import Polygon as ShapelyPolygon, box
import webbrowser
import threading
import time
import getpass
import socket
from datetime import datetime, timedelta

import dash
from dash import dcc, html, Input, Output, State, callback
import plotly.graph_objs as go
import dash_bootstrap_components as dbc
from flask import request

def check_environment():
    """Check if EDEN environment is activated and required modules are available"""
    # Check EDEN environment
    eden_path = "/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1"
    eden_active = eden_path in os.environ.get('PATH', '')
    
    if not eden_active:
        print("⚠️  WARNING: EDEN environment not detected!")
        print("   For best compatibility, activate EDEN environment first:")
        print(f"   source {eden_path}/bin/activate")
        print("")
    
    # Check critical modules
    missing_modules = []
    try:
        import dash
        import dash_bootstrap_components
        import plotly
        print("✓ Dash modules available")
    except ImportError as e:
        missing_modules.append(f"Dash modules: {e}")
    
    try:
        import pandas
        import numpy
        print("✓ Data processing modules available")
    except ImportError as e:
        missing_modules.append(f"Data modules: {e}")
    
    try:
        from astropy.io import fits
        import shapely
        print("✓ Scientific modules available")
    except ImportError as e:
        missing_modules.append(f"Scientific modules: {e}")
    
    if missing_modules:
        print("⚠️  ERROR: Missing required modules!")
        for module in missing_modules:
            print(f"   - {module}")
        print("")
        print("   Solutions:")
        print("   1. Use virtual environment: ./cluster_visualization/scripts/run_dash_app_venv.sh")
        print("   2. Setup virtual environment: ./setup_venv.sh")
        print("   3. Install manually: pip install dash dash-bootstrap-components")
        print("")
        return False
    
    print("✓ All required modules available")
    return True

# Check environment before imports
if not check_environment():
    sys.exit(1)

# Add project root to path for configuration import
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import configuration
from config import get_config
config = get_config()
print("✓ Configuration loaded successfully")

# Add local data modules path
data_modules_path = os.path.join(os.path.dirname(__file__), 'data')
if data_modules_path not in sys.path:
    sys.path.append(data_modules_path)

# Import data handling modules
from data.loader import DataLoader
from data.catred_handler import CATREDHandler
from mermosaic import MOSAICHandler
print("✓ Data modules loaded successfully")

# Import visualization modules
from visualization.traces import TraceCreator
from visualization.figures import FigureManager
print("✓ Visualization modules loaded successfully")

# Import callback modules  
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from callbacks.main_plot import MainPlotCallbacks
from callbacks.catred_callbacks import CATREDCallbacks
from callbacks.ui_callbacks import UICallbacks
from callbacks.phz_callbacks import PHZCallbacks
print("✓ Callback modules loaded successfully")

# Import UI and core modules
from ui.layout import AppLayout
print("✓ UI layout module loaded successfully")

from core.app import ClusterVisualizationCore
print("✓ Core module loaded successfully")

# Add local utils path
parent_dir = os.path.dirname(os.path.dirname(__file__))
utils_path = os.path.join(parent_dir, 'utils')

if utils_path not in sys.path:
    sys.path.append(utils_path)

# Import utilities
from cluster_visualization.utils.myutils import get_xml_element
from cluster_visualization.utils.colordefinitions import colors_list, colors_list_transparent
print(f"✓ Utilities loaded from: {utils_path}")

class ConnectionMonitor:
    """Monitor user connections to detect if anyone has connected to the app"""
    
    def __init__(self):
        self.connections = set()
        self.start_time = datetime.now()
        self.warning_sent = False
        self.monitoring_active = True
        
    def record_connection(self, user_agent=None, ip=None):
        """Record a new connection"""
        connection_id = f"{ip or 'unknown'}:{user_agent or 'unknown'}"
        is_first_connection = len(self.connections) == 0
        self.connections.add(connection_id)
        
        if is_first_connection:
            print(f"✓ User successfully connected at {datetime.now().strftime('%H:%M:%S')}")
            if ip == '127.0.0.1' or ip == 'localhost':
                print("  ✓ SSH tunnel appears to be working correctly")
            print(f"  Browser: {user_agent or 'unknown'}")
            print(f"  Connection from: {ip or 'unknown'}")
            print("")

    def check_connections(self, warn_after_minutes=1):  # Back to 1 minute for production
        """Check if any connections have been made and warn if not"""
        if self.warning_sent or not self.monitoring_active:
            return
            
        elapsed = datetime.now() - self.start_time
        if elapsed > timedelta(minutes=warn_after_minutes) and not self.connections:
            self.warning_sent = True
            elapsed_seconds = elapsed.total_seconds()
            
            # Get the actual hostname
            try:
                hostname = socket.gethostbyaddr(socket.gethostname())[0]
            except:
                hostname = "remotehost"
            
            print("\n" + "="*70)
            print("⚠️  WARNING: No users have connected yet!")
            print(f"   App has been running for {elapsed_seconds/60:.1f} minutes")
            print("")
            print("🔗 REQUIRED: SSH Tunnel Setup")
            print("   This app runs on a remote server and requires SSH tunneling.")
            print("   ")
            print("   1. Open a NEW terminal on your LOCAL machine")
            print("   2. Run this command:")
            print(f"      ssh -L 8050:localhost:8050 {getpass.getuser()}@{hostname}")
            print("   3. Keep that SSH connection alive")
            print("   4. Open your browser to: http://localhost:8050")
            print("")
            print("="*70 + "\n")
    
    def start_monitoring(self, check_interval=30):
        """Start background monitoring thread"""
        def monitor():
            while self.monitoring_active:
                self.check_connections()
                time.sleep(check_interval)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    
    def stop_monitoring(self):
        """Stop the monitoring"""
        self.monitoring_active = False

class ClusterVisualizationApp:
    def __init__(self):
        self.app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        
        # Initialize connection monitoring
        self.connection_monitor = None
        
        # Application state attributes
        self.data_cache = {}
        self.mer_traces_cache = []
        self.current_catred_data = None
        
        # Initialize data handling modules
        self.data_loader = DataLoader(config)
        self.catred_handler = CATREDHandler()
        print("✓ Using modular data handlers")
        
        # Initialize mosaic handler
        self.mosaic_handler = MOSAICHandler(config)
        print("✓ Mosaic handler initialized")
        
        # Initialize visualization modules
        self.trace_creator = TraceCreator(colors_list, colors_list_transparent, self.catred_handler)
        self.figure_manager = FigureManager()
        print("✓ Using modular visualization handlers")
        
        # Initialize UI layout
        self.app.layout = AppLayout.create_layout()
        print("✓ Using modular UI layout")
        
        # Initialize callbacks
        self.setup_callbacks()
        
        # Initialize core application manager
        if ClusterVisualizationCore:
            self.core = ClusterVisualizationCore(self.app)
            print("✓ Using modular core manager")
        else:
            self.core = None
            print("⚠️  Using fallback core functionality")
            
            # Set up connection monitoring for fallback mode
            self.connection_monitor = ConnectionMonitor()
            
            @self.app.server.before_request
            def track_connections():
                user_agent = request.headers.get('User-Agent', '')
                ip = request.environ.get('REMOTE_ADDR', 'unknown')
                # Only track browser connections (not internal Dash requests)
                if 'Mozilla' in user_agent or 'Chrome' in user_agent or 'Safari' in user_agent or 'Firefox' in user_agent:
                    self.connection_monitor.record_connection(user_agent, ip)
        
    def load_data(self, select_algorithm='PZWAV'):
        """Load and prepare all data for visualization"""
        return self.data_loader.load_data(select_algorithm)
    
    def create_traces(self, data, show_polygons=True, show_mer_tiles=False, relayout_data=None, 
                     show_catred_mertile_data=False, manual_mer_data=None, existing_mer_traces=None, 
                     snr_threshold_lower=None, snr_threshold_upper=None):
        """Create all Plotly traces - delegates to trace creator"""
        return self.trace_creator.create_traces(
            data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data,
            manual_mer_data, existing_mer_traces, snr_threshold_lower, snr_threshold_upper
        )
    

    def get_radec_mertile(self, mertileid, data):
        """Load CATRED data for a specific MER tile - delegates to MER handler"""
        return self.catred_handler.get_radec_mertile(mertileid, data)
    
    def load_catred_scatter_data(self, data, relayout_data, catred_mode="unmasked", threshold=0.8, maglim=None):
        """Load MER scatter data for the current zoom window - delegates to MER handler"""
        return self.catred_handler.load_catred_scatter_data(data, relayout_data, catred_mode, threshold, maglim)
    
    def load_mosaic_traces_in_zoom(self, data, relayout_data, opacity=0.5, colorscale='gray'):
        """Load mosaic image traces for MER tiles in the current zoom window"""
        return self.mosaic_handler.load_mosaic_traces_in_zoom(data, relayout_data, opacity, colorscale)
    
    def setup_layout(self):
        """Setup the Dash app layout with side-by-side plots and compact controls"""
        self.app.layout = dbc.Container([
            # Header row
            dbc.Row([
                dbc.Col([
                    html.H1("Cluster Detection Visualization", className="text-center mb-3"),
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
                            html.Div([
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
                            ], className="mb-4"),
                            
                            # SNR Filtering section
                            html.Div([
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
                            ], className="mb-4"),
                            
                            # Redshift Filtering section
                            html.Div([
                                html.Label("Redshift Filtering:", className="fw-bold mb-2"),
                                html.Div(id="redshift-range-display", className="text-center mb-2"),
                                dcc.RangeSlider(
                                    id='redshift-range-slider',
                                    min=0,  # Will be updated dynamically
                                    max=100,  # Will be updated dynamically
                                    step=0.1,
                                    marks={},  # Will be updated dynamically
                                    value=[0, 100],  # Will be updated dynamically
                                    tooltip={"placement": "bottom", "always_visible": True},
                                    allowCross=False
                                ),
                                dbc.Button(
                                    "Apply Redshift Filter",
                                    id="redshift-render-button",
                                    color="secondary",
                                    size="sm",
                                    className="w-100 mt-2",
                                    n_clicks=0,
                                    disabled=True
                                )
                            ], className="mb-4"),

                            # Display options
                            html.Div([
                                html.Label("Display Options:", className="fw-bold mb-2"),
                                
                                html.Div([
                                    dbc.Switch(
                                        id="polygon-switch",
                                        label="Fill polygons",
                                        value=False,
                                    )
                                ], className="mb-2"),
                                
                                html.Div([
                                    dbc.Switch(
                                        id="mer-switch",
                                        label="Show MER tiles",
                                        value=False,
                                    ),
                                    html.Small("(Only with outline polygons)", className="text-muted")
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
                                    dbc.Switch(
                                        id="catred-mertile-switch",
                                        label="High-res MER data",
                                        value=False,
                                    ),
                                    html.Small("(When zoomed < 2°)", className="text-muted")
                                ], className="mb-3"),
                            ], className="mb-4"),
                            
                            # MER Data controls
                            html.Div([
                                html.Label("MER Data Controls:", className="fw-bold mb-2"),
                                
                                html.Div([
                                    dbc.Button(
                                        "🔍 Render MER Data",
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
                                        "🗑️ Clear All MER",
                                        id="mer-clear-button",
                                        color="warning",
                                        size="sm",
                                        className="w-100 mb-2",
                                        n_clicks=0
                                    ),
                                    html.Small("(Remove all MER traces)", className="text-muted d-block text-center")
                                ])
                            ], className="mb-4"),
                            
                            html.Hr(),
                            
                            # Main render button
                            html.Div([
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

    def setup_callbacks(self):
        """Setup Dash callbacks using modular approach"""
        # Use modular callbacks now that imports are working
        if MainPlotCallbacks and CATREDCallbacks and UICallbacks and PHZCallbacks:
            # Use modular callback setup
            print("✓ Setting up modular callbacks")
            
            # Initialize callback handlers
            self.main_plot_callbacks = MainPlotCallbacks(
                self.app, self.data_loader, self.catred_handler, 
                self.trace_creator, self.figure_manager, self.mosaic_handler
            )
            
            self.catred_callbacks = CATREDCallbacks(
                self.app, self.data_loader, self.catred_handler, 
                self.trace_creator, self.figure_manager
            )
            
            self.ui_callbacks = UICallbacks(self.app)
            
            self.phz_callbacks = PHZCallbacks(self.app, self.catred_handler)
            
            print("✓ All modular callbacks initialized")
            
        else:
            # All modular components should be available - this should not happen
            print("❌ ERROR: Modular callback components not available - check imports")
            raise ImportError("Required callback modules not available")
    
    def open_browser(self, port=8050, delay=1.5):
        """Open browser after a short delay"""
        def open_browser_delayed():
            time.sleep(delay)
            webbrowser.open(f'http://localhost:{port}')
        
        browser_thread = threading.Thread(target=open_browser_delayed)
        browser_thread.daemon = True
        browser_thread.start()

    def run(self, host='localhost', port=8050, debug=False, auto_open=True, external_access=False):
        """Run the Dash app using modular core"""
        if self.core:
            # Use modular core
            return self.core.run(host, port, debug, auto_open, external_access)
        else:
            # Core module should always be available - this should not happen
            print("❌ ERROR: Modular core not available - check imports")
            raise ImportError("Required core module not available")
    
def main():
    """Main function to run the app"""
    import sys
    
    # Check for external access flag using modular core if available
    if ClusterVisualizationCore:
        external_access = ClusterVisualizationCore.check_command_line_args()
    else:
        external_access = '--external' in sys.argv or '--remote' in sys.argv
    
    app = ClusterVisualizationApp()
    
    # Try different ports if default is busy using modular core if available
    if app.core:
        app.core.try_multiple_ports(ports=[8050, 8051, 8052, 8053], debug=False, auto_open=False, external_access=external_access)
    else:
        # Fallback implementation
        for port in [8050, 8051, 8052, 8053]:
            try:
                app.run(port=port, debug=False, auto_open=False, external_access=external_access)
                break
            except OSError as e:
                if "Address already in use" in str(e):
                    print(f"Port {port} is busy, trying next port...")
                    continue
                else:
                    raise e

if __name__ == '__main__':
    main()
