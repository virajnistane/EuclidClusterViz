#!/bin/bash

# Cluster Visualization Project Launcher
# This script launches the main cluster visualization tools

echo "=== Cluster Visualization Project ==="
echo "Launching cluster visualization tools..."
echo ""

# Check if the cluster_visualization directory exists
if [ ! -d "cluster_visualization" ]; then
    echo "Error: cluster_visualization directory not found!"
    echo "Please run this script from the ClusterVisualization project root directory."
    exit 1
fi

# Change to the cluster_visualization directory and run the main launcher
cd cluster_visualization/scripts

# Check if the main launcher exists
if [ ! -f "launch.sh" ]; then
    echo "Error: Main launcher script not found!"
    echo "Expected: cluster_visualization/scripts/launch.sh"
    exit 1
fi

# Run the main launcher
./launch.sh
