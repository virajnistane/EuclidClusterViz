#!/bin/bash

# Remote Access Launcher for Cluster Visualization Dash App
# This script helps you run the app on a remote server for local browser access

echo "=== Cluster Visualization - Remote Access Setup ==="
echo ""

# Get server info
HOSTNAME=$(hostname -f 2>/dev/null || hostname)
USERNAME=$(whoami)

echo "Server: $USERNAME@$HOSTNAME"
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
        
        # Check for virtual environment
        if [ -d "venv" ]; then
            echo "Using virtual environment..."
            source venv/bin/activate
            python cluster_visualization/src/cluster_dash_app.py
        elif [ -f "cluster_visualization/src/cluster_dash_app.py" ]; then
            echo "Using EDEN environment..."
            python cluster_visualization/src/cluster_dash_app.py
        else
            echo "Error: Cannot find cluster_dash_app.py"
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
        
        # Check for virtual environment
        if [ -d "venv" ]; then
            echo "Using virtual environment..."
            source venv/bin/activate
            python cluster_visualization/src/cluster_dash_app.py --external
        elif [ -f "cluster_visualization/src/cluster_dash_app.py" ]; then
            echo "Using EDEN environment..."
            python cluster_visualization/src/cluster_dash_app.py --external
        else
            echo "Error: Cannot find cluster_dash_app.py"
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
