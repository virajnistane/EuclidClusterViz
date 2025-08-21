#!/bin/bash

# Environment Setup Script for Cluster Visualization
# This script helps configure the environment for different users

echo "=== Cluster Visualization Environment Setup ==="
echo ""

# Get current user and hostname info
USER_HOME=$(eval echo ~$USER)
HOSTNAME=$(hostname -f 2>/dev/null || hostname)
CURRENT_DIR=$(pwd)

echo "Current user: $USER"
echo "User home: $USER_HOME"
echo "Hostname: $HOSTNAME"
echo "Current directory: $CURRENT_DIR"
echo ""

# Check if we're in the right directory
if [[ ! -f "config.py" ]]; then
    echo "❌ Error: config.py not found in current directory"
    echo "Please run this script from the ClusterVisualization project root directory"
    exit 1
fi

echo "✅ Found config.py in current directory"
echo ""

# Function to prompt for path input
prompt_for_path() {
    local var_name="$1"
    local description="$2"
    local default_value="$3"
    local current_value
    
    echo "Configure $description:"
    echo "  Current default: $default_value"
    read -p "  Enter new path (or press Enter to keep default): " current_value
    
    if [[ -n "$current_value" ]]; then
        echo "  → Will update $var_name to: $current_value"
        # Store for later processing
        eval "NEW_$var_name=\"$current_value\""
    else
        echo "  → Keeping default: $default_value"
    fi
    echo ""
}

echo "=== Path Configuration ==="
echo "You can customize the following paths for your environment:"
echo ""

# Extract current defaults from config.py
BASE_WORKSPACE=$(python3 -c "from config import config; print(config._base_workspace)" 2>/dev/null || echo "/sps/euclid/OU-LE3/CL/ial_workspace/workdir")
EDEN_PATH=$(python3 -c "from config import config; print(config._cvmfs_eden_path)" 2>/dev/null || echo "/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1")

# Prompt for each configurable path
prompt_for_path "BASE_WORKSPACE" "Base Euclid workspace directory" "$BASE_WORKSPACE"
prompt_for_path "EDEN_PATH" "CVMFS EDEN environment path" "$EDEN_PATH"

# Check if any changes were requested
CHANGES_REQUESTED=false
if [[ -n "$NEW_BASE_WORKSPACE" ]] || [[ -n "$NEW_EDEN_PATH" ]]; then
    CHANGES_REQUESTED=true
fi

if [[ "$CHANGES_REQUESTED" == "true" ]]; then
    echo "=== Applying Configuration Changes ==="
    
    # Create backup of original config
    cp config.py config.py.backup
    echo "✅ Created backup: config.py.backup"
    
    # Apply changes to config.py
    if [[ -n "$NEW_BASE_WORKSPACE" ]]; then
        sed -i "s|self._base_workspace = '.*'|self._base_workspace = '$NEW_BASE_WORKSPACE'|g" config.py
        echo "✅ Updated base workspace path"
    fi
    
    if [[ -n "$NEW_EDEN_PATH" ]]; then
        sed -i "s|self._cvmfs_eden_path = '.*'|self._cvmfs_eden_path = '$NEW_EDEN_PATH'|g" config.py
        echo "✅ Updated EDEN path"
    fi
    
    echo ""
else
    echo "No changes requested - keeping current configuration"
    echo ""
fi

# Validate the configuration
echo "=== Validating Configuration ==="
python3 -c "
from config import get_config, validate_environment
config = get_config()
config.print_config_summary()
is_valid, issues = validate_environment()
if not is_valid:
    print('\n❌ Configuration issues found:')
    for issue in issues:
        print(f'  {issue}')
    exit(1)
else:
    print('\n✅ Configuration validation successful!')
"

if [[ $? -eq 0 ]]; then
    echo ""
    echo "=== Setup Complete ==="
    echo "✅ Environment configuration is ready!"
    echo ""
    echo "Next steps:"
    echo "1. Activate EDEN environment (if needed):"
    echo "   source $EDEN_PATH/bin/activate"
    echo ""
    echo "2. Start Jupyter notebook:"
    echo "   jupyter notebook det_clusters_visualization.ipynb"
    echo ""
    echo "3. Or run the Dash app:"
    echo "   cd cluster_visualization/src"
    echo "   python cluster_dash_app.py"
    echo ""
else
    echo ""
    echo "❌ Configuration validation failed!"
    echo "Please check the paths and try again."
    exit 1
fi
