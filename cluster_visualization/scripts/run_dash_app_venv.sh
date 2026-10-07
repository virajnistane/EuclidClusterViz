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

# Background prefetch. The venv (Ceph) and the uv-managed stdlib (/pbs/home) sit on
# network filesystems, and Python reads each imported file one at a time: a cold start
# waited ~80 s on those reads. setup_venv.sh writes the exact files the app loads
# (.pyc, extensions, their shared libraries; in import order) to a manifest; parallel
# readers fetch them into the page cache while the app starts, never delaying it.
# CLUSTERVIZ_NO_PREFETCH=1 disables it; CLUSTERVIZ_PREFETCH_JOBS sets the readers (16).
MANIFEST="$VENV_DIR/.clusterviz-prefetch"
PREFETCH_INFO="off"
start_prefetch() {
    if [ -n "${CLUSTERVIZ_NO_PREFETCH:-}" ]; then
        return
    fi
    if [ ! -s "$MANIFEST" ]; then
        PREFETCH_INFO="no manifest (run ./setup_venv.sh --manifest)"
        return
    fi
    nice -n 10 xargs -a "$MANIFEST" -d '\n' -P "${CLUSTERVIZ_PREFETCH_JOBS:-16}" -n 32 \
        cat > /dev/null 2>&1 &
    PREFETCH_PID=$!
    # Stop the readers if the app exits first (including Ctrl-C)
    trap 'kill "$PREFETCH_PID" 2>/dev/null' EXIT
    PREFETCH_INFO="background, $(wc -l < "$MANIFEST") files"
}

start_prefetch

# Calculate total launcher time (the app's own import/init time is printed by the app)
SCRIPT_END=$(date +%s.%N)
TOTAL_TIME=$(echo "$SCRIPT_END - $SCRIPT_START" | bc)

echo ""
echo "=== Launcher Overhead Summary (app import/init timed separately below) ==="
echo "Launcher total: ${TOTAL_TIME}s"
echo "  - Venv activation: ${VENV_TIME}s"
echo "  - Venv check/sync: ${SYNC_TIME}s"
echo "  - Module prefetch: ${PREFETCH_INFO}"
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
