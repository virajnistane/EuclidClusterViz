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
VENV_DIR="$PROJECT_DIR/venv"

echo "Project directory: $PROJECT_DIR"
echo "Virtual environment: $VENV_DIR"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python -m venv --system-site-packages "$VENV_DIR"
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

# Install required packages from requirements.txt
echo ""
echo "Installing required packages from requirements.txt..."
echo "This may take a few minutes..."

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip install -r "$PROJECT_DIR/requirements.txt"
    if [ $? -eq 0 ]; then
        echo "✓ All packages from requirements.txt installed successfully"
    else
        echo "✗ Failed to install some packages from requirements.txt"
    fi
else
    echo "✗ requirements.txt not found in $PROJECT_DIR"
    exit 1
fi

# Note: Some packages like astropy and shapely may be available from EDEN
# The above will install/upgrade them if needed

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
    ('shapely.geometry', 'shapely'),
    ('healpy', 'healpy'),
    ('PIL', 'Pillow')
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
    echo "Simply run the launcher script: ./launch.sh"
    echo ""
    echo "Or manually:"
    echo "1. Activate EDEN: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate"
    echo "2. Activate venv: source $VENV_DIR/bin/activate"
    echo "3. Run app: python cluster_visualization/src/cluster_dash_app.py"
    echo ""
else
    echo ""
    echo "✗ Setup failed. Please check the error messages above."
    exit 1
fi
