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
VENV_DIR="$PROJECT_DIR/.venv"

echo "Project directory: $PROJECT_DIR"
echo "Virtual environment: $VENV_DIR"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment with pip..."
    python -m venv --system-site-packages "$VENV_DIR"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Check if uv is available in the venv
USE_UV=false
if command -v uv &> /dev/null; then
    echo "✓ uv package manager detected (fast installation mode)"
    USE_UV=true
else
    echo "⚠️  uv not found in virtual environment"
    echo "   Installing uv for faster package management (10-100x speedup)..."
    pip install --upgrade pip
    pip install uv
    
    if [ $? -eq 0 ]; then
        echo "✓ uv installed successfully"
        USE_UV=true
    else
        echo "⚠️  Failed to install uv - falling back to pip"
        echo "   (Installation will be slower but will still work)"
        USE_UV=false
    fi
fi
echo ""

# Upgrade build tools
if [ "$USE_UV" = false ]; then
    echo "Upgrading pip and build tools..."
    pip install --upgrade pip setuptools wheel
fi

# Install package using pyproject.toml
echo ""
echo "Installing cluster-visualization package from pyproject.toml..."
if [ "$USE_UV" = true ]; then
    echo "Using uv for fast installation..."
else
    echo "This may take a few minutes..."
fi

if [ -f "$PROJECT_DIR/pyproject.toml" ]; then
    # Install in editable mode with all dependencies
    if [ "$USE_UV" = true ]; then
        uv pip install -e "$PROJECT_DIR"
    else
        pip install -e "$PROJECT_DIR"
    fi
    
    if [ $? -eq 0 ]; then
        echo "✓ cluster-visualization package installed successfully"
        echo "✓ All runtime dependencies installed from pyproject.toml"
    else
        echo "✗ Failed to install package from pyproject.toml"
        exit 1
    fi
    
    # Optionally install development dependencies
    # Only prompt for user vnistane, auto-skip for others
    CURRENT_USER=$(whoami)
    if [[ "$CURRENT_USER" == "vnistane" ]]; then
        read -p "Install development dependencies (pytest, black, mypy, etc.)? [Y/n] " -n 1 -r
        echo
        # Default to Yes if user just presses Enter (empty REPLY) or types Y/y
        if [[ -z "$REPLY" ]] || [[ $REPLY =~ ^[Yy]$ ]]; then
            if [ "$USE_UV" = true ]; then
                uv pip install -e "$PROJECT_DIR[dev]"
            else
                pip install -e "$PROJECT_DIR[dev]"
            fi
            
            if [ $? -eq 0 ]; then
                echo "✓ Development dependencies installed"
            else
                echo "⚠️  Failed to install some development dependencies"
            fi
        else
            echo "Skipping development dependencies"
        fi
    else
        echo "Skipping development dependencies (for developers, use: pip install -e '.[dev]')"
    fi
else
    echo "✗ pyproject.toml not found in $PROJECT_DIR"
    echo "   Falling back to requirements.txt..."
    
    if [ -f "$PROJECT_DIR/requirements.txt" ]; then
        if [ "$USE_UV" = true ]; then
            uv pip install -r "$PROJECT_DIR/requirements.txt"
        else
            pip install -r "$PROJECT_DIR/requirements.txt"
        fi
        
        if [ $? -eq 0 ]; then
            echo "✓ All packages from requirements.txt installed successfully"
        else
            echo "✗ Failed to install some packages"
            exit 1
        fi
    else
        echo "✗ Neither pyproject.toml nor requirements.txt found!"
        exit 1
    fi
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
    echo "Package installed: cluster-visualization v1.0.0"
    echo ""
    echo "Available commands:"
    echo "  cluster-viz              Launch the Dash application"
    echo "  cluster-viz-test         Run all tests"
    echo ""
    echo "To use the Dash app:"
    echo "  Option 1 (Recommended): ./launch.sh"
    echo "  Option 2: cluster-viz"
    echo "  Option 3: python -m cluster_visualization.src.cluster_dash_app"
    echo ""
    echo "Manual activation:"
    echo "1. Activate EDEN: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate"
    echo "2. Activate venv: source $VENV_DIR/bin/activate"
    echo "3. Run: cluster-viz"
    echo ""
else
    echo ""
    echo "✗ Setup failed. Please check the error messages above."
    exit 1
fi
