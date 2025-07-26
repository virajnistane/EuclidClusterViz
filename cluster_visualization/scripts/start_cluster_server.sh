#!/bin/bash

# Standalone Cluster Visualization Server Launcher
# This script can be run from anywhere and will launch the HTTP server

echo "=== Standalone Cluster Visualization Server ==="

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
            echo "   Please manually run: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate"
            echo "   Then rerun this script"
            exit 1
        fi
    else
        echo "✓ EDEN environment already active"
    fi
}

# Activate environment
check_eden_environment
echo ""

# Default project directory
PROJECT_DIR="/pbs/home/v/vnistane/ClusterVisualization/cluster_visualization"

# Check if project directory was provided as argument
if [ $# -gt 0 ]; then
    PROJECT_DIR="$1"
fi

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Project directory does not exist: $PROJECT_DIR"
    echo "Usage: $0 [project_directory] [port]"
    exit 1
fi

# Default port
PORT=8000
if [ $# -gt 1 ]; then
    PORT="$2"
fi

echo "Project directory: $PROJECT_DIR"
echo "Starting server on port: $PORT"
echo ""

# Check if HTML files exist
if [ ! -d "$PROJECT_DIR/output/current" ] || [ -z "$(ls -A $PROJECT_DIR/output/current/*.html 2>/dev/null)" ]; then
    echo "No HTML files found in $PROJECT_DIR/output/current/"
    echo ""
    echo "Please generate HTML files first:"
    echo "  cd $PROJECT_DIR"
    echo "  python src/generate_standalone_html.py"
    echo ""
    echo "Or use the project launcher:"
    echo "  cd $PROJECT_DIR && ./scripts/launch.sh"
    exit 1
fi

# Launch the emergency server
echo "Launching HTTP server..."

# Get the script directory to find emergency_server.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "$SCRIPT_DIR/emergency_server.py" "$PROJECT_DIR" "$PORT"
