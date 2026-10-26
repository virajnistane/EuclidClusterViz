#!/bin/bash
#
# Launch ClusterViz from the Apptainer image (euclid_cluster_viz.sif).
#
# Standalone: copy this file next to euclid_cluster_viz.sif and run it from anywhere; the
# repository is not needed. Build the image with "make sif".
#
# Usage:
#   ./launch_sif.sh                          # default config baked into the image
#   ./launch_sif.sh --config my_config.ini   # your own config (relative paths are fine)
#   ./launch_sif.sh --external --log-level DEBUG
#   ./launch_sif.sh --help-launcher          # this help; --help shows the app's options
#
# Environment:
#   CLUSTERVIZ_SIF    image to run (default: euclid_cluster_viz.sif next to this script)
#   CLUSTERVIZ_BIND   extra bind paths, comma-separated (e.g. /data,/scratch/$USER)
#   CLUSTERVIZ_*      other app variables (e.g. CLUSTERVIZ_LOG_LEVEL) pass through

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIF="${CLUSTERVIZ_SIF:-$SCRIPT_DIR/euclid_cluster_viz.sif}"

if [ "${1:-}" = "--help-launcher" ]; then
    sed -n '2,/^$/s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"
    exit 0
fi

if [ ! -f "$SIF" ]; then
    echo "Error: image not found: $SIF" >&2
    echo "Build it with 'make sif' or set CLUSTERVIZ_SIF=/path/to/euclid_cluster_viz.sif" >&2
    exit 1
fi

if command -v apptainer > /dev/null; then
    RUNTIME=apptainer
elif command -v singularity > /dev/null; then
    RUNTIME=singularity
else
    echo "Error: neither apptainer nor singularity is on PATH" >&2
    exit 1
fi

# Top-level directory of a path: /pbs/home/v/user -> /pbs
top_dir() {
    local rest="${1#/}"
    echo "/${rest%%/*}"
}

# Make --config absolute, so it resolves the same inside the container, and remember
# the file so it gets bound too.
args=()
config_file=""
expect_config=false
for arg in "$@"; do
    if $expect_config; then
        arg="$(realpath -m -- "$arg")"
        config_file="$arg"
        expect_config=false
    elif [ "$arg" = "--config" ]; then
        expect_config=true
    elif [[ "$arg" == --config=* ]]; then
        arg="--config=$(realpath -m -- "${arg#--config=}")"
        config_file="${arg#--config=}"
    fi
    args+=("$arg")
done

# A whole top-level directory is bound only if the image does not use it itself
# (binding the host's /opt would hide the image's /opt/venv, for example).
home_bind="$(top_dir "$HOME")"
case "$home_bind" in
    /|/opt|/app|/usr|/etc|/bin|/sbin|/lib|/lib64|/var|/tmp|/proc|/sys|/dev|/run|/root)
        home_bind="$HOME" ;;
esac

# Bind what exists on this host, skipping paths an earlier bind already covers:
#   /sps         Euclid data
#   /cvmfs       Rich-CL parameters for the members "Magnitude limit" switch
#   $HOME (top)  disk caches in ~/.cache/clusterviz* (/pbs on CC-IN2P3, where $HOME
#                is not mounted into the container on its own)
#   config file  the --config file itself (not its directory, which may be /opt)
binds=()
for dir in /sps /cvmfs "$home_bind" ${config_file:+"$config_file"}; do
    [ -e "$dir" ] || continue
    covered=false
    for b in ${binds[@]+"${binds[@]}"}; do
        if [ "$dir" = "$b" ] || [[ "$dir" == "$b"/* ]]; then
            covered=true
        fi
    done
    $covered || binds+=("$dir")
done
if [ -n "${CLUSTERVIZ_BIND:-}" ]; then
    IFS=',' read -r -a extra <<< "$CLUSTERVIZ_BIND"
    binds+=("${extra[@]}")
fi
bind_list="$(IFS=,; echo "${binds[*]-}")"

echo "ClusterViz: $RUNTIME run $(basename "$SIF")${bind_list:+ (bind: $bind_list)}"
exec "$RUNTIME" run ${bind_list:+--bind "$bind_list"} "$SIF" ${args[@]+"${args[@]}"}
