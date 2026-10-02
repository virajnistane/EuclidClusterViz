#!/bin/bash

# Cluster Visualization Dash App Launcher with Virtual Environment
# Automatically sets up and uses virtual environment

# Enable timing measurements
SCRIPT_START=$(date +%s.%N)

echo "=== Cluster Visualization Dash App (Virtual Environment) ==="

# Get project directory (go up two levels from scripts directory)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

echo "Project directory: $PROJECT_DIR"
echo ""

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Setting it up..."
    echo "This will only happen once and may take a few minutes."
    echo ""
    
    if [ -f "$PROJECT_DIR/setup_venv.sh" ]; then
        "$PROJECT_DIR/setup_venv.sh"
        if [ $? -ne 0 ]; then
            echo "✗ Virtual environment setup failed"
            exit 1
        fi
    else
        echo "✗ Setup script not found: $PROJECT_DIR/setup_venv.sh"
        exit 1
    fi
else
    echo "✓ Virtual environment found"
fi

# Activate virtual environment
echo "Activating virtual environment..."
VENV_START=$(date +%s.%N)
source "$VENV_DIR/bin/activate"
VENV_END=$(date +%s.%N)
VENV_TIME=$(echo "$VENV_END - $VENV_START" | bc)

# Reject stale environments created before the Python 3.14 minimum.
if ! python -c "import sys; sys.exit(sys.version_info < (3, 14))"; then
    echo "✗ Python 3.14 or newer is required in $VENV_DIR"
    echo "   Remove the old virtual environment and rerun setup_venv.sh"
    exit 1
fi

# Verify activation
if [[ "$VIRTUAL_ENV" == "$VENV_DIR" ]]; then
    echo "✓ Virtual environment activated: $VIRTUAL_ENV"
    echo "   [Time: ${VENV_TIME}s]"
else
    echo "✗ Failed to activate virtual environment"
    exit 1
fi

# Check for critical dependencies and install if missing
echo ""
echo "Checking critical dependencies..."
DEPS_START=$(date +%s.%N)



# Check other critical modules
IMPORT_START=$(date +%s.%N)
# Cheap presence check (no heavy imports); the app itself imports them right after
python -c "
import importlib.util, sys
mods = ['plotly', 'pandas', 'numpy', 'astropy', 'shapely', 'dash']
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    print('✗ Missing dependency: ' + ', '.join(missing))
    sys.exit(1)
print('✓ All core dependencies available')
"

if [ $? -ne 0 ]; then
    echo "Installing missing dependencies from pyproject.toml..."
    export UV_LINK_MODE=copy
    uv pip install -e "$PROJECT_DIR"
    if [ $? -ne 0 ]; then
        echo "✗ Failed to install dependencies"
        echo "   Please run: pip install -e $PROJECT_DIR"
        exit 1
    fi
    echo "✓ Dependencies installed"
fi
IMPORT_END=$(date +%s.%N)
IMPORT_TIME=$(echo "$IMPORT_END - $IMPORT_START" | bc)
echo "   [import check time: ${IMPORT_TIME}s]"

DEPS_END=$(date +%s.%N)
DEPS_TIME=$(echo "$DEPS_END - $DEPS_START" | bc)
echo "   [Total dependency check time: ${DEPS_TIME}s]"

# Calculate total startup time
SCRIPT_END=$(date +%s.%N)
TOTAL_TIME=$(echo "$SCRIPT_END - $SCRIPT_START" | bc)

echo ""
echo "=== Startup Performance Summary ==="
echo "Total startup time: ${TOTAL_TIME}s"
echo "  - Venv activation: ${VENV_TIME}s"
echo "  - Dependency checks: ${DEPS_TIME}s"
echo ""

echo "Starting Dash app server..."
echo "The app will automatically open in your browser"
# echo "Available at: http://localhost:8050 (or next available port)"
echo ""
echo "Features:"
echo "  • Algorithm switching (PZWAV/AMICO)"
echo "  • Interactive plotting with zoom/pan"
echo "  • Polygon fill toggle"
echo "  • MER tile display option"
echo "  • Free aspect ratio zoom (default)"
echo "  • Custom config file support (use --config /path/to/config.ini)"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Time the app startup
APP_START=$(date +%s.%N)

# Pass all arguments to the Python script (allows --config, --external, etc.)
cd "$PROJECT_DIR"
python cluster_visualization/src/cluster_dash_app.py "$@"
