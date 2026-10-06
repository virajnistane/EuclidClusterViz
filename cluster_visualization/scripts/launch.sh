#!/bin/bash

# Universal Cluster Visualization Launcher
# Provides standalone HTML visualization solutions
#
# Usage:
#   ./launch.sh                              # Launch Dash app (default)
#   ./launch.sh --config /path/to/custom.ini # Launch with custom config
#   ./launch.sh --test-dependencies          # Test dependencies only
#   ./launch.sh --help                       # Show help message

echo "=== Cluster Visualization Launcher ==="

# Parse command line arguments
APP_ARGS=()
TEST_DEPENDENCIES=false
SHOW_HELP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            if [ "$#" -lt 2 ]; then
                echo "Error: --config requires a file path"
                exit 1
            fi
            APP_ARGS+=("--config" "$2")
            echo "Using custom config: $2"
            shift 2
            ;;
        --test-dependencies)
            TEST_DEPENDENCIES=true
            shift
            ;;
        --help|-h)
            SHOW_HELP=true
            shift
            ;;
        --debug)
            APP_ARGS+=("--debug")
            shift
            ;;
        --external|--remote)
            APP_ARGS+=("$1")
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Show help if requested
if [ "$SHOW_HELP" = true ]; then
    echo ""
    echo "USAGE:"
    echo "  ./launch.sh [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  --config FILE            Use custom configuration file"
    echo "  --test-dependencies      Test all dependencies and exit"
    echo "  --help, -h               Show this help message"
    echo "  --debug                  Run the app in debug mode with hot-reloading"
    echo "  --external               Allow external network access"
    echo "  --remote                 Alias for --external"
    echo ""
    echo "EXAMPLES:"
    echo "  ./launch.sh"
    echo "    Launch the Dash application with default configuration"
    echo ""
    echo "  ./launch.sh --config /path/to/custom.ini"
    echo "    Launch with a custom configuration file"
    echo ""
    echo "  ./launch.sh --test-dependencies"
    echo "    Test all Python dependencies and project structure"
    echo ""
    echo "  ./launch.sh --debug"
    echo "    Run the Dash application in debug mode with hot-reloading"
    echo ""
    echo "DESCRIPTION:"
    echo "  Launches the Euclid Cluster Visualization Dash application."
    echo "  The application provides interactive visualization of cluster"
    echo "  detection data with algorithm switching, filtering, and analysis tools."
    echo ""
    echo "  Features:"
    echo "    - Interactive cluster detection visualization"
    echo "    - Algorithm switching (PZWAV/AMICO/BOTH)"
    echo "    - SNR and redshift filtering"
    echo "    - CATRED high-resolution data integration"
    echo "    - Mosaic image overlays"
    echo "    - HEALPix mask visualization"
    echo "    - Cluster analysis tools (cutouts, PHZ plots)"
    echo ""
    exit 0
fi

# If testing dependencies, run tests and exit
if [ "$TEST_DEPENDENCIES" = true ]; then
    echo "Testing the application virtual environment..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
    cd "$PROJECT_DIR"

    # Create the environment, or re-sync it when uv.lock/pyproject.toml changed (a
    # fast no-op otherwise). CLUSTERVIZ_NO_AUTOSYNC=1 skips the check.
    if [ -z "${CLUSTERVIZ_NO_AUTOSYNC:-}" ]; then
        if ! "$PROJECT_DIR/setup_venv.sh" --if-stale; then
            echo "✗ Virtual environment setup failed"
            exit 1
        fi
    elif [ ! -d "$PROJECT_DIR/.venv" ]; then
        echo "✗ Virtual environment not found (CLUSTERVIZ_NO_AUTOSYNC is set): run ./setup_venv.sh"
        exit 1
    fi
    source "$PROJECT_DIR/.venv/bin/activate"
    if ! python -c "import sys; sys.exit(sys.version_info < (3, 14))"; then
        echo "✗ Python 3.14 or newer is required in .venv."
        echo "   Run ./setup_venv.sh to recreate the environment."
        exit 1
    fi
    
    # Test all dependencies
    echo "Testing all dependencies..."
    echo ""
    
    echo "1. Basic Python modules:"
    python -c "import os, sys, json, pickle; print('✓ Standard library OK')" 2>/dev/null || echo "✗ Standard library issues"
    
    echo "2. Scientific Python:"
    python -c "import pandas, numpy; print('✓ pandas/numpy OK')" 2>/dev/null || echo "✗ pandas/numpy issues"
    python -c "from astropy.io import fits; print('✓ astropy OK')" 2>/dev/null || echo "✗ astropy issues"
    python -c "from shapely.geometry import Polygon; print('✓ shapely OK')" 2>/dev/null || echo "✗ shapely issues"
    python -c "import healpy; print('✓ healpy OK')" 2>/dev/null || echo "✗ healpy missing (required for CATRED data)"
    
    echo "3. Plotting libraries:"
    python -c "import plotly.graph_objs as go; print('✓ plotly OK')" 2>/dev/null || echo "✗ plotly issues"
    python -c "import dash; print('✓ dash OK')" 2>/dev/null || echo "✗ dash issues"
    
    echo "4. Custom modules:"
    python -c "
import sys
import os
utils_dir = os.path.join(os.getcwd(), 'cluster_visualization/utils')
sys.path.append(utils_dir)
from cluster_visualization.utils.myutils import get_xml_element
from cluster_visualization.utils.colordefinitions import colors_list
print('✓ Custom modules OK')
" 2>/dev/null || echo "✗ Custom modules issues"
    
    echo ""
    echo "5. Project structure:"
    if [ -f "config.ini" ]; then
        echo "✓ Configuration file exists"
    else
        echo "✗ Configuration file missing (config.ini)"
    fi
    
    if [ -d "cluster_visualization/src" ]; then
        echo "✓ Source code directory exists"
    else
        echo "✗ Source code directory missing"
    fi
    
    if [ -f "cluster_visualization/src/cluster_dash_app.py" ]; then
        echo "✓ Main Dash application exists"
    else
        echo "✗ Main Dash application missing"
    fi
    
    echo ""
    python -c "
import plotly.graph_objs as go
import pandas, numpy
from astropy.io import fits
from shapely.geometry import Polygon
print('✓ All dependencies working correctly')
" 2>/dev/null || echo "✗ Some dependencies have issues"
    
    exit 0
fi

echo "Launching Dash application..."

# Get the script directory and move to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_DIR"

# Launch Dash app with virtual environment
echo "This will automatically install missing modules if needed"
echo "Features: Algorithm switching, interactive plotting, real-time updates"
if [ -n "$CONFIG_ARG" ]; then
    echo "Config: $CONFIG_ARG"
fi
echo ""
./cluster_visualization/scripts/run_dash_app_venv.sh "${APP_ARGS[@]}"
