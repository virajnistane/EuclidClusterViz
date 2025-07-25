#!/bin/bash

# Cluster Visualization Dash App Launcher
# Automatically runs the Dash app server and opens browser

echo "=== Cluster Visualization Dash App ==="

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
            exit 1
        fi
    else
        echo "✓ EDEN environment already active"
    fi
}

# Activate environment
check_eden_environment
echo ""

# Get the script directory and move to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "Starting Dash app server..."
echo "The app will automatically open in your browser"
echo "Available at: http://localhost:8050 (or next available port)"
echo ""
echo "Features:"
echo "  • Algorithm switching (PZWAV/AMICO)"
echo "  • Interactive plotting with zoom/pan"
echo "  • Polygon fill toggle"
echo "  • MER tile display option"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the Dash app
python src/cluster_dash_app.py
