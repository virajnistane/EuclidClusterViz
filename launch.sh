#!/bin/bash

# Cluster Visualization Project Launcher
# This script launches the main cluster visualization tools
#
# Usage:
#   ./launch.sh                              # Default config
#   ./launch.sh --config /path/to/custom.ini # Custom config

echo "=== Cluster Visualization Project ==="
echo "Launching cluster visualization tools..."
echo ""

# Parse command line arguments for config file
CONFIG_ARG=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_ARG="--config $2"
            echo "Using custom config: $2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--config /path/to/config.ini]"
            exit 1
            ;;
    esac
done
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

# Run the main launcher with any provided arguments
./launch.sh $CONFIG_ARG
