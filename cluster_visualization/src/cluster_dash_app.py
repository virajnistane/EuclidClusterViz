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
- Custom configuration file support via command-line argument

REQUIREMENTS:
- Must activate EDEN environment first: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
- This provides required packages: astropy, plotly, pandas, numpy, shapely, dash

USAGE:
- Default config: python cluster_dash_app.py
- Custom config:  python cluster_dash_app.py --config /path/to/custom_config.ini
- External access: python cluster_dash_app.py --external
- Combined:        python cluster_dash_app.py --config /path/to/config.ini --external
"""

import argparse
# import json
import os
# import pickle
import sys
import threading
import time
import webbrowser
# from datetime import datetime, timedelta

import dash
import dash_bootstrap_components as dbc
import diskcache
from dash import DiskcacheManager
import numpy as np
import pandas as pd
import plotly.graph_objs as go
from dash import Input, Output, State, callback, dcc, html
from flask import request


def check_environment():
    """Check EDEN environment activation and required package versions."""
    import importlib.metadata

    eden_path = "/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1"
    if eden_path not in os.environ.get("PATH", "") and not os.environ.get("CLUSTERVIZ_SKIP_EDEN_CHECK"):
        print("⚠️  WARNING: EDEN environment not detected!")
        print(f"   source {eden_path}/bin/activate")
        print("")

    required = ["dash", "dash-bootstrap-components", "plotly", "numpy", "pandas", "astropy", "shapely"]
    missing = []
    for pkg in required:
        try:
            importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            missing.append(pkg)

    if missing:
        print("⚠️  ERROR: Missing required packages: " + ", ".join(missing))
        print("   Solutions:")
        print("   1. Use virtual environment: ./cluster_visualization/scripts/run_dash_app_venv.sh")
        print("   2. Setup virtual environment: ./setup_venv.sh")
        print("   3. Install manually: pip install " + " ".join(missing))
        print("")
        return False

    print("✓ All required packages available")
    return True


# Check environment before imports
if not check_environment():
    sys.exit(1)

# Add project root to path for configuration import
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add src directory to path for config import
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import configuration
from config import get_config


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Cluster Visualization Dash App",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default config (config_local.ini or config.ini)
  %(prog)s --config /path/to/custom.ini       # Use custom config file
  %(prog)s --external                         # Allow external access (0.0.0.0)
  %(prog)s --config custom.ini --external     # Custom config with external access
        """,
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom configuration file (default: auto-detect config_local.ini or config.ini)",
    )
    parser.add_argument(
        "--external",
        action="store_true",
        help="Allow external access to the app (binds to 0.0.0.0 instead of 127.0.0.1)",
    )
    parser.add_argument(
        "--remote", action="store_true", help="Alias for --external (for backward compatibility)"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Run the app in debug mode with hot-reloading"
    )
    return parser.parse_args()


# Parse arguments first
args = parse_arguments()

# Load configuration with custom file if specified
if args.config:
    print(f"📋 Using custom configuration file: {args.config}")
    config = get_config(config_file=args.config)
else:
    print("📋 Using default configuration (auto-detect)")
    config = get_config()
print("✓ Configuration loaded successfully")

# Add local data modules path
data_modules_path = os.path.join(os.path.dirname(__file__), "data")
if data_modules_path not in sys.path:
    sys.path.append(data_modules_path)

from data.catred_handler import CATREDHandler

# Import data handling modules
from data.loader import DataLoader
from mermosaic import MOSAICHandler

print("✓ Data modules loaded successfully")

from visualization.figures import FigureManager

# Import visualization modules
from visualization.traces import TraceCreator

print("✓ Visualization modules loaded successfully")

# Import callback modules
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from callbacks.catred_callbacks import CATREDCallbacks
from callbacks.cluster_modal_callbacks import ClusterModalCallbacks
from callbacks.main_plot import MainPlotCallbacks
from callbacks.mosaic_callback import MOSAICCallbacks
from callbacks.phz_callbacks import PHZCallbacks
from callbacks.ui_callbacks import UICallbacks

print("✓ Callback modules loaded successfully")

# Import UI and core modules
from ui.layout import AppLayout

print("✓ UI layout module loaded successfully")

from core.app import ClusterVisualizationCore

print("✓ Core module loaded successfully")

# Add local utils path
parent_dir = os.path.dirname(os.path.dirname(__file__))
utils_path = os.path.join(parent_dir, "utils")

if utils_path not in sys.path:
    sys.path.append(utils_path)

from cluster_visualization.utils.colordefinitions import colors_list, colors_list_transparent

# Import utilities
from cluster_visualization.utils.myutils import get_xml_element

print(f"✓ Utilities loaded from: {utils_path}")


class ClusterVisualizationApp:
    def __init__(self):
        # Custom CSS file path
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "ui", "enhanced_styles.css"
        )

        # Initialize Dash app with Bootstrap and custom CSS
        external_stylesheets = [
            dbc.themes.BOOTSTRAP,
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",
        ]

        # Background callback manager for long_callback / background=True support
        _bg_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "clusterviz_bg")
        _bg_cache = diskcache.Cache(_bg_cache_dir)
        bg_callback_manager = DiskcacheManager(_bg_cache)

        self.app = dash.Dash(
            __name__,
            external_stylesheets=external_stylesheets,
            background_callback_manager=bg_callback_manager,
        )

        # Add custom CSS if file exists
        if os.path.exists(css_path):
            try:
                with open(css_path, "r") as f:
                    custom_css = f.read()
                self.app.index_string = f"""
                <!DOCTYPE html>
                <html>
                    <head>
                        {{%metas%}}
                        <title>{{%title%}}</title>
                        {{%favicon%}}
                        {{%css%}}
                        <style>
                            {custom_css}
                        </style>
                    </head>
                    <body>
                        {{%app_entry%}}
                        <footer>
                            {{%config%}}
                            {{%scripts%}}
                            {{%renderer%}}
                        </footer>
                    </body>
                </html>
                """
                print("✓ Custom enhanced styling loaded")
            except Exception as e:
                print(f"⚠️  Warning: Could not load custom CSS: {e}")
        else:
            print(f"⚠️  Warning: Custom CSS file not found at {css_path}")

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
        self.core = ClusterVisualizationCore(self.app)
        print("✓ Using modular core manager")

    def setup_callbacks(self):
        """Setup Dash callbacks using modular approach"""
        # Use modular callbacks now that imports are working
        if (
            MainPlotCallbacks
            and CATREDCallbacks
            and UICallbacks
            and PHZCallbacks
            and ClusterModalCallbacks
        ):
            # Use modular callback setup
            print("✓ Setting up modular callbacks")

            # Initialize callback handlers
            self.main_plot_callbacks = MainPlotCallbacks(
                self.app,
                self.data_loader,
                self.catred_handler,
                self.trace_creator,
                self.figure_manager,
            )

            self.catred_callbacks = CATREDCallbacks(
                self.app,
                self.data_loader,
                self.catred_handler,
                self.trace_creator,
                self.figure_manager,
            )

            self.mosaic_callbacks = MOSAICCallbacks(
                self.app,
                self.data_loader,
                self.mosaic_handler,
                self.trace_creator,
                self.figure_manager,
            )

            self.ui_callbacks = UICallbacks(self.app, config, self.data_loader)

            self.phz_callbacks = PHZCallbacks(self.app, self.catred_handler, self.data_loader)

            # 🆕 Initialize cluster modal callbacks
            self.cluster_modal_callbacks = ClusterModalCallbacks(
                app=self.app,
                data_loader=self.data_loader,
                catred_handler=self.catred_handler,
                mosaic_handler=self.mosaic_handler,
                trace_creator=self.trace_creator,
                figure_manager=self.figure_manager,
            )

            print("✓ All modular callbacks initialized")

        else:
            # All modular components should be available - this should not happen
            print("❌ ERROR: Modular callback components not available - check imports")
            raise ImportError("Required callback modules not available")

    def open_browser(self, port=8050, delay=1.5):
        """Open browser after a short delay"""

        def open_browser_delayed():
            time.sleep(delay)
            webbrowser.open(f"http://localhost:{port}")

        browser_thread = threading.Thread(target=open_browser_delayed)
        browser_thread.daemon = True
        browser_thread.start()

    def run(self, host="localhost", port=8050, debug=False, auto_open=True, external_access=False):
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
    # Arguments are already parsed globally as 'args'

    # Check for external access flag
    external_access = args.external or args.remote
    debug = args.debug
    
    if external_access:
        print("🌐 External access enabled (binding to 0.0.0.0)")
    else:
        print("🔒 Local access only (binding to 127.0.0.1)")

    app = ClusterVisualizationApp()

    # # Pre-warm disk cache in background so first render is fast
    # def _prewarm():
    #     try:
    #         for algo in ("PZWAV", "AMICO", "BOTH"):
    #             app.data_loader.load_data(select_algorithm=algo)
    #             print(f"✓ Pre-warm complete: {algo}")
    #     except Exception as e:
    #         print(f"⚠️  Pre-warm failed: {e}")

    # threading.Thread(target=_prewarm, daemon=True).start()
    # print("🔥 Background data pre-warm started")

    # Derive per-user ports from UID so multiple users on same node never collide.
    # UID is stable across all cluster nodes (set at account creation).
    uid_offset = os.getuid() % 1000
    user_ports = [
        8050 + uid_offset,
        8050 + uid_offset + 1000,
        8050 + uid_offset + 2000,
    ]

    if app.core:
        app.core.try_multiple_ports(
            ports=user_ports,
            debug=debug,
            auto_open=False,
            external_access=external_access,
        )
    else:
        for port in user_ports:
            try:
                app.run(port=port, debug=debug, auto_open=False, external_access=external_access)
                break
            except SystemExit:
                print(f"Port {port} is busy, trying next port...")
                continue
            except OSError as e:
                if "Address already in use" in str(e):
                    print(f"Port {port} is busy, trying next port...")
                    continue
                else:
                    raise e


if __name__ == "__main__":
    main()
