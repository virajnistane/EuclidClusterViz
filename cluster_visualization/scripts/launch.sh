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

# Test if HTML file exists in output/current
if [ ! -f "cluster_visualization/output/current/cluster_visualization_comparison.html" ]; then
    echo "HTML visualization not found. Generating..."
    python cluster_visualization/src/generate_standalone_html.py --algorithm BOTH
    if [ $? -ne 0 ]; then
        echo "Error: Could not generate HTML file"
        exit 1
    fi
fi

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
    echo "1) Dash App with Virtual Env (Recommended)" >&2
    echo "2) Simple Server (Always works)" >&2
    echo "3) Standalone HTML (Open directly in browser)" >&2
    echo "4) Generate new HTML file" >&2
    echo "5) Test dependencies" >&2
    echo "" >&2
    read -p "Choose an option (1-5): " choice >&2
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

# Function to launch simple server
launch_simple() {
    echo "Launching simple HTTP server..."
    echo "Will try ports 8000, 8001, 8002 if needed..."
    echo "Press Ctrl+C to stop"
    
    # Get the actual script directory (this file's directory)
    # Handle case where script is called from different locations
    if [[ "${BASH_SOURCE[0]}" == *"/scripts/launch.sh" ]]; then
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
    else
        # Fallback: assume we're in project root and find scripts directory
        PROJECT_ROOT="$(pwd)"
        SCRIPT_DIR="$PROJECT_ROOT/cluster_visualization/scripts"
    fi
    
    # Try different ports if 8000 is in use
    for port in 8000 8001 8002; do
        echo "Trying port $port..."
        
        # Check if port is available first
        if netstat -ln 2>/dev/null | grep -q ":$port "; then
            echo "Port $port is already in use, trying next..."
            continue
        fi
        
        # Use the emergency server from the scripts directory
        echo "Starting server on port $port..."
        python "$SCRIPT_DIR/emergency_server.py" "$PROJECT_ROOT/cluster_visualization" $port
        break
    done
}

# Function to open HTML directly
open_html() {
    echo "Opening HTML file directly in browser..."
    if [ -f "cluster_visualization/output/current/cluster_visualization_comparison.html" ]; then
        html_file="cluster_visualization/output/current/cluster_visualization_comparison.html"
    else
        echo "Comparison file not found, generating it first..."
        python cluster_visualization/src/generate_standalone_html.py --algorithm BOTH
        html_file="cluster_visualization/output/current/cluster_visualization_comparison.html"
    fi
    
    if command -v firefox >/dev/null 2>&1; then
        firefox "$html_file" &
        echo "Opened $html_file in Firefox"
    elif command -v google-chrome >/dev/null 2>&1; then
        google-chrome "$html_file" &
        echo "Opened $html_file in Chrome"
    elif command -v chromium >/dev/null 2>&1; then
        chromium "$html_file" &
        echo "Opened $html_file in Chromium"
    else
        echo "No supported browser found. Please open $html_file manually"
    fi
}

# Function to generate new HTML
generate_html() {
    echo "Generating new HTML visualization..."
    python cluster_visualization/src/generate_standalone_html.py --algorithm BOTH
    if [ $? -eq 0 ]; then
        echo "✓ HTML file generated successfully"
        echo "File: cluster_visualization/output/current/cluster_visualization_comparison.html"
        size=$(ls -lh cluster_visualization/output/current/cluster_visualization_comparison.html | awk '{print $5}')
        echo "Size: $size"
    else
        echo "✗ Error generating HTML file"
    fi
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
    
    echo "3. Plotting libraries:"
    python -c "import plotly.graph_objs as go; print('✓ plotly OK')" 2>/dev/null || echo "✗ plotly issues"
    
    echo "4. Custom modules:"
    python -c "
import sys
import os
utils_dir = os.path.join(os.getcwd(), 'cluster_visualization/utils')
sys.path.append(utils_dir)
from myutils import get_xml_element
from colordefinitions import colors_list
print('✓ Custom modules OK')
" 2>/dev/null || echo "✗ Custom modules issues"
    
    echo ""
    echo "5. Data files:"
    if [ -f "cluster_visualization/output/current/cluster_visualization_comparison.html" ]; then
        size=$(ls -lh "cluster_visualization/output/current/cluster_visualization_comparison.html" | awk '{print $5}')
        echo "✓ HTML visualization exists ($size)"
    else
        echo "✗ HTML visualization missing"
    fi
    
    echo ""
    if test_dependencies; then
        echo "✓ All dependencies working correctly"
    else
        echo "✗ Some dependencies have issues"
    fi
}

# Main execution
choice=$(get_choice)
choice=$(echo "$choice" | tr -d '[:space:]')  # Remove whitespace

case $choice in
    1)
        launch_dash_venv
        ;;
    2)
        launch_simple
        ;;
    3)
        open_html
        ;;
    4)
        generate_html
        ;;
    5)
        test_all
        ;;
    *)
        echo "Invalid choice '$choice'. Using recommended option (Dash App with Virtual Env)..."
        launch_dash_venv
        ;;
esac
