#!/bin/bash

# Remote Access Launcher for Cluster Visualization Dash App
# This script helps you run the app on a remote server for local browser access
#
# Usage:
#   ./run_remote_dash.sh                              # Default config
#   ./run_remote_dash.sh --config /path/to/custom.ini # Custom config

echo "=== Cluster Visualization - Remote Access Setup ==="
echo ""

# Parse command line arguments for config file
CONFIG_ARG=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_ARG="--config $2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--config /path/to/config.ini]"
            exit 1
            ;;
    esac
done

# Get server info
HOSTNAME=$(hostname -f 2>/dev/null || hostname)
USERNAME=$(whoami)

echo "Server: $USERNAME@$HOSTNAME"
if [ -n "$CONFIG_ARG" ]; then
    echo "Config: $CONFIG_ARG"
fi
echo ""

echo "Choose your access method:"
echo ""
echo "1) SSH Port Forwarding (Recommended - Most Secure)"
echo "   - Runs app on localhost (remote server)"
echo "   - Access via SSH tunnel from local machine"
echo ""
echo "2) Direct Network Access"
echo "   - Runs app on all interfaces (0.0.0.0)"
echo "   - Access directly from local machine"
echo ""
echo "3) Show SSH tunnel command only"
echo ""

read -p "Select option (1-3): " choice

case $choice in
    1)
        echo ""
        echo "=== SSH Port Forwarding Setup ==="
        echo ""
        echo "STEP 1: On your LOCAL machine, create SSH tunnel:"
        echo "        ssh -L 8050:localhost:8050 $USERNAME@$HOSTNAME"
        echo ""
        echo "STEP 2: Keep that SSH connection open"
        echo ""
        echo "STEP 3: Open http://localhost:8050 in your LOCAL browser"
        echo ""
        echo "Starting app on remote server (localhost mode)..."
        echo "Press Ctrl+C to stop"
        echo ""
        
        # Get the script directory and project root
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
        
        # Check for virtual environment
        if [ -d "$PROJECT_ROOT/venv" ]; then
            echo "Using virtual environment..."
            cd "$PROJECT_ROOT"
            source venv/bin/activate
            python cluster_visualization/src/cluster_dash_app.py $CONFIG_ARG
        elif [ -f "$PROJECT_ROOT/cluster_visualization/src/cluster_dash_app.py" ]; then
            echo "Using EDEN environment..."
            cd "$PROJECT_ROOT"
            python cluster_visualization/src/cluster_dash_app.py $CONFIG_ARG
        else
            echo "Error: Cannot find cluster_dash_app.py"
            echo "Project root: $PROJECT_ROOT"
            exit 1
        fi
        ;;
        
    2)
        echo ""
        echo "=== Direct Network Access Setup ==="
        echo ""
        echo "The app will be accessible from any machine that can reach this server."
        echo ""
        echo "Access URLs:"
        echo "  - http://$HOSTNAME:8050"
        echo "  - Or use server IP address"
        echo ""
        echo "NOTE: Ensure firewall allows port 8050"
        echo ""
        echo "Starting app for external access..."
        echo "Press Ctrl+C to stop"
        echo ""
        
        # Get the script directory and project root
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
        
        # Check for virtual environment
        if [ -d "$PROJECT_ROOT/venv" ]; then
            echo "Using virtual environment..."
            cd "$PROJECT_ROOT"
            source venv/bin/activate
            python cluster_visualization/src/cluster_dash_app.py --external $CONFIG_ARG
        elif [ -f "$PROJECT_ROOT/cluster_visualization/src/cluster_dash_app.py" ]; then
            echo "Using EDEN environment..."
            cd "$PROJECT_ROOT"
            python cluster_visualization/src/cluster_dash_app.py --external $CONFIG_ARG
        else
            echo "Error: Cannot find cluster_dash_app.py"
            echo "Checking paths:"
            echo "  Virtual env: $(ls -la "$PROJECT_ROOT/venv" 2>/dev/null || echo 'not found')"
            echo "  App file: $(ls -la "$PROJECT_ROOT/cluster_visualization/src/cluster_dash_app.py" 2>/dev/null || echo 'not found')"
            echo "  Project root: $PROJECT_ROOT"
            exit 1
        fi
        ;;
        
    3)
        echo ""
        echo "=== SSH Tunnel Commands ==="
        echo ""
        echo "Run this command on your LOCAL machine:"
        echo ""
        echo "    ssh -L 8050:localhost:8050 $USERNAME@$HOSTNAME"
        echo ""
        echo "Alternative ports (if 8050 is busy):"
        echo "    ssh -L 8051:localhost:8051 $USERNAME@$HOSTNAME"
        echo "    ssh -L 8052:localhost:8052 $USERNAME@$HOSTNAME"
        echo ""
        echo "Then start the app normally on this server and access"
        echo "http://localhost:8050 from your local browser."
        echo ""
        ;;
        
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac
