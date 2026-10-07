#!/bin/bash
#
# Create or update the project's .venv with uv (Python 3.14, locked dependencies).
#
# Usage:
#   ./setup_venv.sh                 # Create/update .venv (keeps extras installed before)
#   ./setup_venv.sh --dev           # Also install the dev extra (pytest, black, mypy, ...)
#   ./setup_venv.sh --docs          # Also install the docs extra (sphinx, myst-parser, ...)
#   ./setup_venv.sh --test          # Also install the test extra (pytest-cov, pytest-mock)
#   ./setup_venv.sh --notebooks     # Also install the notebooks extra (matplotlib, ipykernel)
#   ./setup_venv.sh --no-extras     # Drop all extras
#   ./setup_venv.sh --if-stale      # Do nothing when .venv already matches uv.lock/pyproject.toml
#   ./setup_venv.sh --recreate      # Delete .venv and rebuild it from scratch
#   ./setup_venv.sh --manifest      # Only rewrite the launcher's prefetch list (after big code changes)
#
# The launchers run "--if-stale" before every start, so a pull that changes uv.lock
# re-syncs the environment once. Set CLUSTERVIZ_NO_AUTOSYNC=1 to skip that check.

set -euo pipefail

PYTHON_VERSION="3.14"

usage() {
    sed -n '3,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

IF_STALE=false
RECREATE=false
MANIFEST_ONLY=false
NO_EXTRAS=false
REQUESTED_EXTRAS=()
if [ "${DEV:-}" = "1" ]; then
    REQUESTED_EXTRAS+=(dev)
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev) REQUESTED_EXTRAS+=(dev); shift ;;
        --docs) REQUESTED_EXTRAS+=(docs); shift ;;
        --test) REQUESTED_EXTRAS+=(test); shift ;;
        --notebooks) REQUESTED_EXTRAS+=(notebooks); shift ;;
        --all-extras) REQUESTED_EXTRAS+=(dev docs test); shift ;;
        --no-extras) NO_EXTRAS=true; shift ;;
        --if-stale) IF_STALE=true; shift ;;
        --recreate) RECREATE=true; shift ;;
        --manifest) MANIFEST_ONLY=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${UV_PROJECT_ENVIRONMENT:-$PROJECT_DIR/.venv}"
# Records what the last successful sync installed; compared on --if-stale
STAMP_FILE="$VENV_DIR/.clusterviz-sync"
# Files the app imports, read in the background by the launcher (run_dash_app_venv.sh)
MANIFEST_FILE="$VENV_DIR/.clusterviz-prefetch"

if [ ! -f "$PROJECT_DIR/pyproject.toml" ]; then
    echo "✗ pyproject.toml not found in $PROJECT_DIR"
    exit 1
fi

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum | cut -d' ' -f1
    else
        shasum -a 256 | cut -d' ' -f1
    fi
}

# Hash of everything that decides the environment's contents
deps_hash() {
    {
        cat "$PROJECT_DIR/pyproject.toml"
        if [ -f "$PROJECT_DIR/uv.lock" ]; then cat "$PROJECT_DIR/uv.lock"; fi
        echo "python=$PYTHON_VERSION"
    } | sha256
}

# Space-separated, sorted, de-duplicated
normalize_extras() {
    printf '%s\n' "$@" | sed '/^$/d' | sort -u | tr '\n' ' ' | sed 's/ $//'
}

stamp_value() {
    if [ -f "$STAMP_FILE" ]; then
        sed -n "s/^$1=//p" "$STAMP_FILE"
    fi
}

# Never fatal: without a manifest the launcher just skips the prefetch. .pyc files are
# written so the list names what Python really reads.
write_manifest() {
    env -u PYTHONDONTWRITEBYTECODE "$VENV_DIR/bin/python" \
        "$PROJECT_DIR/cluster_visualization/scripts/write_prefetch_manifest.py" \
        "$PROJECT_DIR" "$MANIFEST_FILE" \
        || echo "Warning: prefetch manifest not written (the app still starts, without prefetch)"
}

venv_python_ok() {
    [ -x "$VENV_DIR/bin/python" ] \
        && "$VENV_DIR/bin/python" -c "import sys; sys.exit(sys.version_info < (${PYTHON_VERSION/./, }))" 2>/dev/null
}

# Extras to install: those of the last sync plus the requested ones. A plain
# "uv sync" removes extras it is not asked for, so an automatic re-sync must
# repeat them or it would uninstall pytest/sphinx.
if [ "$NO_EXTRAS" = true ]; then
    PREVIOUS_EXTRAS=""
else
    PREVIOUS_EXTRAS="$(stamp_value extras)"
fi
# shellcheck disable=SC2086
EXTRAS="$(normalize_extras $PREVIOUS_EXTRAS ${REQUESTED_EXTRAS[@]+"${REQUESTED_EXTRAS[@]}"})"

is_up_to_date() {
    [ "$RECREATE" = false ] \
        && venv_python_ok \
        && [ "$(stamp_value hash)" = "$(deps_hash)" ] \
        && [ "$(stamp_value extras)" = "$EXTRAS" ] \
        && [ -s "$MANIFEST_FILE" ]
}

if [ "$MANIFEST_ONLY" = true ]; then
    if ! venv_python_ok; then
        echo "✗ No usable Python $PYTHON_VERSION environment in $VENV_DIR; run ./setup_venv.sh first"
        exit 1
    fi
    cd "$PROJECT_DIR"
    write_manifest
    exit 0
fi

if [ "$IF_STALE" = true ] && is_up_to_date; then
    echo "✓ Environment up to date ($VENV_DIR)"
    exit 0
fi

# One sync at a time (two launches starting together)
if command -v flock >/dev/null 2>&1; then
    exec 9>"$PROJECT_DIR/.venv.lock"
    flock 9
    # Another process may have synced while we waited
    if [ "$IF_STALE" = true ] && is_up_to_date; then
        echo "✓ Environment up to date ($VENV_DIR)"
        exit 0
    fi
fi

echo "=== Cluster Visualization - Virtual Environment Setup ==="
if [ "$IF_STALE" = true ]; then
    echo "Environment is missing or out of date (uv.lock / pyproject.toml changed); syncing..."
fi

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

cd "$PROJECT_DIR"
export UV_PROJECT_ENVIRONMENT="$VENV_DIR"
export UV_PYTHON_DOWNLOADS=automatic
export UV_LINK_MODE=copy

echo "Project directory: $PROJECT_DIR"
echo "Virtual environment: $VENV_DIR"
echo "Extras: ${EXTRAS:-none}"

if [ "$RECREATE" = true ] && [ -e "$VENV_DIR" ]; then
    echo "Removing $VENV_DIR (--recreate)..."
    rm -rf -- "$VENV_DIR"
fi

echo "Ensuring a Python $PYTHON_VERSION interpreter is available through uv..."
if venv_python_ok; then
    echo "Reusing existing Python $PYTHON_VERSION+ environment."
else
    if [ -e "$VENV_DIR" ]; then
        echo "Existing environment is invalid or uses an unsupported Python version; recreating it with uv."
        "$UV_BIN" venv --clear --python "$PYTHON_VERSION" "$VENV_DIR"
    else
        "$UV_BIN" venv --python "$PYTHON_VERSION" "$VENV_DIR"
    fi
fi

SYNC_ARGS=(sync --project "$PROJECT_DIR" --python "$PYTHON_VERSION" --locked)
for extra in $EXTRAS; do
    SYNC_ARGS+=(--extra "$extra")
done
echo "Installing locked project dependencies with uv..."
"$UV_BIN" "${SYNC_ARGS[@]}"

COMPLETION_DIR="$HOME/.local/share/bash-completion/completions"
COMPLETION_FILE="$COMPLETION_DIR/clusterviz-launch"
mkdir -p "$COMPLETION_DIR"
install -m 0644 "$PROJECT_DIR/cluster_visualization/scripts/launch_completion.bash" "$COMPLETION_FILE"

touch "$HOME/.bashrc"
if ! grep -Fq 'bash-completion/completions/clusterviz-launch' "$HOME/.bashrc"; then
    printf '\n# ClusterViz launch.sh argument completion\nsource "$HOME/.local/share/bash-completion/completions/clusterviz-launch"\n' >> "$HOME/.bashrc"
fi

echo "Testing runtime imports (the first run on a cold node can take a minute)..."
"$VENV_DIR/bin/python" -c "
import importlib, sys, time
# As in cluster_dash_app.py: dash would import IPython/ipykernel (dev extra), slow on
# network storage, and the app never needs them
sys.modules.setdefault('IPython', None)
for name in ('numpy', 'astropy.io.fits', 'pandas', 'scipy', 'shapely.geometry', 'PIL',
             'healpy', 'plotly', 'dash', 'dash_bootstrap_components'):
    t0 = time.perf_counter()
    print(f'  {name:<26}', end='', flush=True)
    importlib.import_module(name)
    print(f'{time.perf_counter() - t0:6.1f} s', flush=True)
"

echo "Writing the launcher's prefetch list..."
write_manifest

printf 'hash=%s\nextras=%s\n' "$(deps_hash)" "$EXTRAS" > "$STAMP_FILE"

echo ""
echo "=== Setup Complete ==="
echo "Python: $("$VENV_DIR/bin/python" --version)"
echo "Virtual environment: $VENV_DIR"
echo "Extras: ${EXTRAS:-none}"
echo "Bash completion: $COMPLETION_FILE"
echo ""
if [[ " $EXTRAS " != *" dev "* ]]; then
    echo "Development tools (pytest, black, mypy, ...): ./setup_venv.sh --dev"
fi
echo "Run the application with ./launch.sh (or: make run) or activate .venv/bin/activate."
