#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OP_RUN_ENV_FILE="${OP_RUN_ENV_FILE:-${SCRIPT_DIR}/op.env}"

if [[ -z "${ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT:-}" ]]; then
    case "$(uname -s)" in
        Darwin)
            ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
            ;;
        Linux)
            ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT="$HOME/.1password/agent.sock"
            ;;
        *)
            ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT=""
            ;;
    esac
fi

require_ssh_agent=1

if [[ ${1:-} == "--no-ssh-agent" ]]; then
    require_ssh_agent=0
    shift
fi

if [[ $# -eq 0 ]]; then
    echo "usage: $0 [--no-ssh-agent] <ansible command> [args ...]" >&2
    exit 1
fi

if ! command -v op >/dev/null 2>&1; then
    echo "op CLI is required" >&2
    exit 1
fi

if ! command -v ssh-add >/dev/null 2>&1; then
    echo "ssh-add is required" >&2
    exit 1
fi

if [[ ! -f "$OP_RUN_ENV_FILE" ]]; then
    echo "op run env file is required: $OP_RUN_ENV_FILE" >&2
    echo "Copy op.env.example to op.env and fill in your 1Password secret references." >&2
    exit 1
fi

configure_1password_ssh_agent() {
    if [[ -n ${SSH_AUTH_SOCK:-} ]] && ssh-add -l >/dev/null 2>&1; then
        return 0
    fi

    if [[ -n "${ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT:-}" ]] && [[ -S "$ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT" ]]; then
        export SSH_AUTH_SOCK="$ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT"
    fi

    if [[ -z ${SSH_AUTH_SOCK:-} ]] || ! ssh-add -l >/dev/null 2>&1; then
        cat >&2 <<'EOF'
1Password SSH agent is not ready.

macOS: Enable the SSH agent in 1Password Settings -> Developer -> SSH Agent.
Linux: Enable the SSH agent in 1Password Settings -> Developer -> SSH Agent.
        The default socket path is ~/.1password/agent.sock.

Alternatively, export SSH_AUTH_SOCK pointing to any SSH agent that holds
the correct key before calling this script.
EOF
        exit 1
    fi
}

if [[ "$require_ssh_agent" -eq 1 ]]; then
    configure_1password_ssh_agent
fi

exec op run --env-file="$OP_RUN_ENV_FILE" -- "$@"