#!/bin/bash

# Virtual Environment Setup for Cluster Visualization Dash App
# This script creates a virtual environment with all required dependencies

echo "=== Cluster Visualization - Virtual Environment Setup ==="

# Check and activate EDEN environment first
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

# Activate EDEN first
check_eden_environment

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/cluster_dash_venv"

echo "Project directory: $PROJECT_DIR"
echo "Virtual environment: $VENV_DIR"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install required packages
echo ""
echo "Installing required packages..."
echo "This may take a few minutes..."

# Install packages one by one to catch any issues
packages=(
    "dash==2.14.1"
    "dash-bootstrap-components==1.5.0"
    "plotly==5.17.0"
    "pandas==2.1.4"
    "numpy==1.24.3"
)

# Note: astropy and shapely should be available from EDEN
# But we'll install them if needed

for package in "${packages[@]}"; do
    echo "Installing $package..."
    pip install "$package"
    if [ $? -eq 0 ]; then
        echo "✓ $package installed successfully"
    else
        echo "✗ Failed to install $package"
    fi
done

# Try to install astropy and shapely if not available from EDEN
echo ""
echo "Checking scientific packages..."

python -c "from astropy.io import fits; print('✓ astropy available')" 2>/dev/null || {
    echo "Installing astropy..."
    pip install astropy==5.3.4
}

python -c "from shapely.geometry import Polygon; print('✓ shapely available')" 2>/dev/null || {
    echo "Installing shapely..."
    pip install shapely==2.0.2
}

# Test all imports
echo ""
echo "Testing all imports..."
python -c "
import sys
success = True

modules = [
    ('dash', 'dash'),
    ('dash_bootstrap_components', 'dash-bootstrap-components'),
    ('plotly', 'plotly'),
    ('pandas', 'pandas'),
    ('numpy', 'numpy'),
    ('astropy.io.fits', 'astropy'),
    ('shapely.geometry', 'shapely')
]

for module, name in modules:
    try:
        __import__(module)
        print(f'✓ {name} import successful')
    except ImportError as e:
        print(f'✗ {name} import failed: {e}')
        success = False

if success:
    print('')
    print('🎉 All modules imported successfully!')
    print('Virtual environment is ready for the Dash app.')
else:
    print('')
    print('⚠️  Some modules failed to import.')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "=== Setup Complete ==="
    echo "Virtual environment created at: $VENV_DIR"
    echo ""
    echo "To use the Dash app:"
    echo "1. Activate EDEN: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate"
    echo "2. Activate venv: source $VENV_DIR/bin/activate"
    echo "3. Run app: python cluster_visualization/src/cluster_dash_app.py"
    echo ""
    echo "Or use the launcher script: ./cluster_visualization/scripts/run_dash_app_venv.sh"
else
    echo ""
    echo "✗ Setup failed. Please check the error messages above."
    exit 1
fi
