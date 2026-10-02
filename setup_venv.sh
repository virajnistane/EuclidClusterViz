#!/bin/bash

set -euo pipefail

echo "=== Cluster Visualization - Virtual Environment Setup ==="

UV_BIN="$(command -v uv || true)"
if [ -z "$UV_BIN" ] && [ -x "$HOME/.local/bin/uv" ]; then
    UV_BIN="$HOME/.local/bin/uv"
fi

if [ -z "$UV_BIN" ]; then
    if ! command -v curl >/dev/null 2>&1; then
        echo "✗ curl is required to install uv in your user scope."
        exit 1
    fi

    echo "uv not found; installing it in your user scope..."
    export UV_INSTALL_DIR="$HOME/.local/bin"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV_BIN="$UV_INSTALL_DIR/uv"
fi

if [ ! -x "$UV_BIN" ]; then
    echo "✗ uv installation did not produce an executable at $UV_BIN"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${UV_PROJECT_ENVIRONMENT:-$PROJECT_DIR/.venv}"

if [ ! -f "$PROJECT_DIR/pyproject.toml" ]; then
    echo "✗ pyproject.toml not found in $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"
export UV_PROJECT_ENVIRONMENT="$VENV_DIR"
export UV_PYTHON_DOWNLOADS=automatic

echo "Project directory: $PROJECT_DIR"
echo "Virtual environment: $VENV_DIR"
echo "Ensuring a Python 3.14 interpreter is available through uv..."

if [ -x "$VENV_DIR/bin/python" ] \
    && "$VENV_DIR/bin/python" -c "import sys; sys.exit(sys.version_info < (3, 14))"; then
    echo "Reusing existing Python 3.14+ environment."
else
    if [ -e "$VENV_DIR" ]; then
        echo "Existing environment is invalid or uses an unsupported Python version; recreating it with uv."
        "$UV_BIN" venv --clear --python 3.14 "$VENV_DIR"
    else
        "$UV_BIN" venv --python 3.14 "$VENV_DIR"
    fi
fi

echo "Installing locked project dependencies with uv..."
"$UV_BIN" sync --project "$PROJECT_DIR" --python 3.14 --locked

COMPLETION_DIR="$HOME/.local/share/bash-completion/completions"
COMPLETION_FILE="$COMPLETION_DIR/clusterviz-launch"
mkdir -p "$COMPLETION_DIR"
install -m 0644 "$PROJECT_DIR/cluster_visualization/scripts/launch_completion.bash" "$COMPLETION_FILE"

touch "$HOME/.bashrc"
if ! grep -Fq 'bash-completion/completions/clusterviz-launch' "$HOME/.bashrc"; then
    printf '\n# ClusterViz launch.sh argument completion\nsource "$HOME/.local/share/bash-completion/completions/clusterviz-launch"\n' >> "$HOME/.bashrc"
fi

if [ "$(whoami)" = "vnistane" ]; then
    read -r -p "Install development dependencies (pytest, black, mypy, etc.)? [Y/n] " answer
    if [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]]; then
        "$UV_BIN" sync --project "$PROJECT_DIR" --python 3.14 --locked --extra dev
    else
        echo "Skipping development dependencies."
    fi
else
    echo "Skipping development dependencies (run: $UV_BIN sync --extra dev)."
fi

echo "Testing runtime imports..."
"$VENV_DIR/bin/python" -c "
import astropy.io.fits
import dash
import dash_bootstrap_components
import healpy
import matplotlib
import numpy
import pandas
import PIL
import plotly
import scipy
import shapely.geometry
"

echo ""
echo "=== Setup Complete ==="
echo "Python: $("$VENV_DIR/bin/python" --version)"
echo "Virtual environment: $VENV_DIR"
echo "Bash completion: $COMPLETION_FILE"
echo ""
echo "Run the application with ./launch.sh or activate .venv/bin/activate."
