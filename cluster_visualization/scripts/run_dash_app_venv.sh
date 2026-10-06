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

# Create the environment, or re-sync it when uv.lock/pyproject.toml changed (a
# fast no-op otherwise). CLUSTERVIZ_NO_AUTOSYNC=1 skips the check.
SYNC_START=$(date +%s.%N)
if [ -z "${CLUSTERVIZ_NO_AUTOSYNC:-}" ]; then
    if ! "$PROJECT_DIR/setup_venv.sh" --if-stale; then
        echo "✗ Virtual environment setup failed"
        exit 1
    fi
elif [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "✗ Virtual environment not found (CLUSTERVIZ_NO_AUTOSYNC is set): run ./setup_venv.sh"
    exit 1
fi
SYNC_TIME=$(echo "$(date +%s.%N) - $SYNC_START" | bc)

# Activate virtual environment
echo "Activating virtual environment..."
VENV_START=$(date +%s.%N)
source "$VENV_DIR/bin/activate"
VENV_END=$(date +%s.%N)
VENV_TIME=$(echo "$VENV_END - $VENV_START" | bc)

# Reject stale environments created before the Python 3.14 minimum.
if ! python -c "import sys; sys.exit(sys.version_info < (3, 14))"; then
    echo "✗ Python 3.14 or newer is required in $VENV_DIR"
    echo "   Rebuild it: ./setup_venv.sh --recreate"
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

# No separate dependency check: setup_venv.sh --if-stale (above) keeps .venv in sync
# with uv.lock and import-tests it after each sync
if [ -n "${CLUSTERVIZ_NO_AUTOSYNC:-}" ]; then
    echo "Note: CLUSTERVIZ_NO_AUTOSYNC is set; if the app fails to import, run ./setup_venv.sh"
fi

# Warm the page cache for the files the app imports at startup. The venv (Ceph) and the
# uv-managed stdlib (/pbs/home) sit on network filesystems: a cold import reads ~2,700
# modules one file at a time (~80 s). Reading them first in parallel turns that into a
# few large concurrent batches. Disable with CLUSTERVIZ_NO_PREFETCH=1.
# Package list from `python -X importtime` of cluster_dash_app (top-level modules only).
PREFETCH_PKGS="astropy astropy_iers_data erfa pandas numpy dash dash_bootstrap_components
    plotly _plotly_utils narwhals flask werkzeug jinja2 markupsafe click blinker itsdangerous
    PIL requests urllib3 charset_normalizer idna certifi yaml pyparsing dateutil pytz psutil
    diskcache packaging importlib_metadata zipp platformdirs typing_extensions.py"

prefetch_imports() {
    local site_packages stdlib python_home p
    local targets=()
    site_packages=$(echo "$VIRTUAL_ENV"/lib/python3.*/site-packages)
    python_home=$(sed -n 's/^home = //p' "$VIRTUAL_ENV/pyvenv.cfg")
    stdlib=$(echo "$python_home"/../lib/python3.*)

    for p in $PREFETCH_PKGS; do
        [ -e "$site_packages/$p" ] && targets+=("$site_packages/$p")
    done
    [ -d "$stdlib" ] && targets+=("$stdlib")
    [ ${#targets[@]} -eq 0 ] && return

    # Test suites are never imported at startup and are a large share of the files.
    find "${targets[@]}" \
        \( -name tests -o -name test -o -name idlelib -o -name tkinter -o -name ensurepip \) -prune \
        -o -type f \( -name '*.py' -o -name '*.pyc' -o -name '*.so' \) -print0 2>/dev/null |
        xargs -0 -P 32 -n 64 cat > /dev/null 2>&1
}

PREFETCH_TIME=0
if [ -z "$CLUSTERVIZ_NO_PREFETCH" ]; then
    echo ""
    echo "Prefetching Python modules into page cache..."
    PREFETCH_START=$(date +%s.%N)
    prefetch_imports
    PREFETCH_END=$(date +%s.%N)
    PREFETCH_TIME=$(echo "$PREFETCH_END - $PREFETCH_START" | bc)
    echo "   [prefetch: ${PREFETCH_TIME}s]"
fi

# Calculate total launcher time (the app's own import/init time is printed by the app)
SCRIPT_END=$(date +%s.%N)
TOTAL_TIME=$(echo "$SCRIPT_END - $SCRIPT_START" | bc)

echo ""
echo "=== Launcher Overhead Summary (app import/init timed separately below) ==="
echo "Launcher total: ${TOTAL_TIME}s"
echo "  - Venv activation: ${VENV_TIME}s"
echo "  - Venv check/sync: ${SYNC_TIME}s"
echo "  - Module prefetch: ${PREFETCH_TIME}s"
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
