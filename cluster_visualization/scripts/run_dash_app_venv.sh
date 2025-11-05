#!/bin/bash

# Cluster Visualization Dash App Launcher with Virtual Environment
# Automatically sets up and uses virtual environment

echo "=== Cluster Visualization Dash App (Virtual Environment) ==="

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

# Activate EDEN environment
check_eden_environment

# Get project directory (go up two levels from scripts directory)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

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
source "$VENV_DIR/bin/activate"

# Verify activation
if [[ "$VIRTUAL_ENV" == "$VENV_DIR" ]]; then
    echo "✓ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "✗ Failed to activate virtual environment"
    exit 1
fi

# Check for critical dependencies and install if missing
echo ""
echo "Checking critical dependencies..."

# Check healpy specifically since it's often missing
python -c "import healpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  healpy not found, installing..."
    pip install "healpy>=1.16.0"
    if [ $? -eq 0 ]; then
        echo "✓ healpy installed successfully"
    else
        echo "✗ Failed to install healpy"
        echo "   You may need to install it manually: pip install healpy"
        exit 1
    fi
else
    echo "✓ healpy available"
fi

# Check other critical modules
python -c "
try:
    import plotly
    import pandas
    import numpy
    import astropy
    import shapely
    import dash
    print('✓ All core dependencies available')
except ImportError as e:
    print(f'✗ Missing dependency: {e}')
    print('   Installing missing dependencies...')
    exit(1)
" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "Installing missing dependencies from requirements.txt..."
    pip install -r "$PROJECT_DIR/requirements.txt"
    if [ $? -ne 0 ]; then
        echo "✗ Failed to install dependencies"
        echo "   Please run: pip install -r requirements.txt"
        exit 1
    fi
    echo "✓ Dependencies installed"
fi

echo ""
echo "Starting Dash app server..."
echo "The app will automatically open in your browser"
echo "Available at: http://localhost:8050 (or next available port)"
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

# Pass all arguments to the Python script (allows --config, --external, etc.)
cd "$PROJECT_DIR"
python cluster_visualization/src/cluster_dash_app.py "$@"
