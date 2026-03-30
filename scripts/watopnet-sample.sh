#!/bin/bash
# Launch the Watcher Operational Network.
#
# Runs the watcher server and boot/management server.
# The watcher server binds to the external host; the boot server stays on localhost.
#
# Environment variable overrides (all optional):
#   WATOPNET_VENV        Path to a venv activate script. Sourced if the file exists;
#                        skipped with a warning if set but not found; ignored if unset.
#                        (default: not set — assumes caller is already in the right env)
#
#   WATOPNET_CONFIG_DIR  Directory containing keri/cf/watopnet.json.
#                        KERI's Configer appends keri/cf/ internally, so this should point
#                        to the directory *above* keri/cf/ (e.g. scripts/, not scripts/keri/cf/).
#                        (default: the scripts/ directory, so local dev works after 'source env.sh')
#
#   WATOPNET_HOST        External host for the watcher server.
#                        (default: 0.0.0.0)
#
#   WATOPNET_BOOT_HOST   Host for the boot/management server. Keep on localhost in production.
#                        (default: 127.0.0.1)
#
#   WATOPNET_HTTP_PORT   Watcher server port. (default: 7632)
#   WATOPNET_BOOT_PORT   Boot/management server port. (default: 7631)
#
# Local dev usage:
#   source scripts/env.sh
#   ./scripts/watopnet-sample.sh
#
# Production usage:
#   WATOPNET_VENV=/opt/healthkeri/watopnet/venv/bin/activate \
#   WATOPNET_CONFIG_DIR=/opt/healthkeri/watopnet/config \
#   ./scripts/watopnet-sample.sh

# Resolve the directory this script lives in, whether or not env.sh has been sourced.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# --- Venv activation ---
if [[ -n "${WATOPNET_VENV:-}" ]]; then
    if [[ -f "${WATOPNET_VENV}" ]]; then
        # shellcheck disable=SC1090
        source "${WATOPNET_VENV}"
    else
        echo "WARN: WATOPNET_VENV set but not found at '${WATOPNET_VENV}', skipping activation." >&2
    fi
fi

# --- Config directory ---
# KERI's Configer appends keri/cf/ internally, so this should point to the directory
# *above* keri/cf/ (e.g. scripts/, not scripts/keri/cf/).
[[ -z "${WATOPNET_CONFIG_DIR:-}" ]] && ConfigDir="${SCRIPT_DIR}" || ConfigDir="${WATOPNET_CONFIG_DIR}"

# --- External host for the watcher server ---
[[ -z "${WATOPNET_HOST:-}" ]] && Host="0.0.0.0" || Host="${WATOPNET_HOST}"

# --- Boot server host (localhost only in production) ---
[[ -z "${WATOPNET_BOOT_HOST:-}" ]] && BootHost="127.0.0.1" || BootHost="${WATOPNET_BOOT_HOST}"

# --- Ports ---
[[ -z "${WATOPNET_HTTP_PORT:-}" ]] && HttpPort="7632" || HttpPort="${WATOPNET_HTTP_PORT}"
[[ -z "${WATOPNET_BOOT_PORT:-}" ]] && BootPort="7631" || BootPort="${WATOPNET_BOOT_PORT}"

# --- Production resource limits ---
export KERI_BASER_MAP_SIZE=1099511627776
ulimit -S -n 65536

# --- Launch ---
watopnet start \
    --config-dir "${ConfigDir}" \
    --host "${Host}" \
    --http "${HttpPort}" \
    --boothost "${BootHost}" \
    --bootport "${BootPort}"