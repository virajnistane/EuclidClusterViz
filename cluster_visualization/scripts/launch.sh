#!/bin/bash

# Universal Cluster Visualization Launcher
# Provides standalone HTML visualization solutions

echo "=== Cluster Visualization Launcher ==="
echo "Testing available solutions..."

# Check and activate EDEN environment if needed
check_eden_environment() {
    if [[ ":$PATH:" != *":/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/"* ]]; then
        echo "⚠️  EDEN environment not detected!"
        echo "   Attempting to activate EDEN environment..."
        
        if [ -f "/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate" ]; then
            source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
            echo "✓ EDEN environment activated"
        else
            echo "✗ EDEN environment not available at /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/"
            echo "   Please ensure CVMFS is mounted and EDEN is available"
            echo "   Or manually activate: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate"
            return 1
        fi
    else
        echo "✓ EDEN environment already active"
    fi
    return 0
}

# Activate environment
if ! check_eden_environment; then
    echo "Warning: Continuing without EDEN environment - some features may not work"
fi
echo ""

# Get the script directory and move to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_DIR"

# Function to test dependencies
test_dependencies() {
    echo "Testing Python dependencies..."
    python -c "
import plotly.graph_objs as go
import pandas, numpy
from astropy.io import fits
from shapely.geometry import Polygon
print('Dependencies test passed')
" 2>/dev/null
    return $?
}

# Function to get user choice
get_choice() {
    echo "" >&2
    echo "Available options:" >&2
    echo "1) Dash App with Virtual Env" >&2
    echo "2) Test dependencies" >&2
    echo "" >&2
    read -p "Choose an option (1-2): " choice >&2
    echo "$choice"
}

# Function to launch Dash app with virtual environment
launch_dash_venv() {
    echo "Launching Dash app with virtual environment..."
    echo "This will automatically install missing modules if needed"
    echo "Features: Algorithm switching, interactive plotting, real-time updates"
    echo "The app will automatically open in your browser"
    echo ""
    ./cluster_visualization/scripts/run_dash_app_venv.sh
}

# Function to test all dependencies
test_all() {
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
    if test_dependencies; then
        echo "✓ All dependencies working correctly"
    else
        echo "✗ Some dependencies have issues"
    fi
}

# Main execution
choice=1 # $(get_choice)
choice=$(echo "$choice" | tr -d '[:space:]')  # Remove whitespace

case $choice in
    1)
        launch_dash_venv
        ;;
    2)
        test_all
        ;;
    *)
        echo "Invalid choice '$choice'. Using recommended option (Dash App with Virtual Env)..."
        launch_dash_venv
        ;;
esac
