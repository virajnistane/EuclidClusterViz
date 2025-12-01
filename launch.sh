#!/bin/bash

# Cluster Visualization Project Launcher
# This script launches the main cluster visualization tools
#
# Usage:
#   ./launch.sh                              # Launch Dash app (default)
#   ./launch.sh --config /path/to/custom.ini # Launch with custom config
#   ./launch.sh --test-dependencies          # Test dependencies only
#   ./launch.sh --help                       # Show help message

echo "=== Cluster Visualization Project ==="

# Parse command line arguments
CONFIG_ARG=""
TEST_DEPENDENCIES=false
SHOW_HELP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_ARG="--config $2"
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

echo "Launching cluster visualization tools..."
echo ""

# Pass arguments to the actual launcher script

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
if [ "$TEST_DEPENDENCIES" = true ]; then
    ./launch.sh --test-dependencies $CONFIG_ARG
else
    ./launch.sh $CONFIG_ARG
fi
