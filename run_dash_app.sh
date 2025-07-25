#!/bin/bash

# Direct Dash App Launcher
# Simple script to run the Dash app from anywhere

echo "=== Starting Cluster Visualization Dash App ==="

# Check EDEN environment
if [[ ":$PATH:" != *":/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/"* ]]; then
    echo "⚠️  WARNING: EDEN environment not detected!"
    echo "   This app requires the EDEN-3.1 scientific Python environment."
    echo "   Please run: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate"
    echo "   Then rerun this script."
    echo ""
    exit 1
fi

# Navigate to the project directory (assuming script is in ClusterVisualization/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Run the Dash app
python cluster_visualization/src/cluster_dash_app.py
