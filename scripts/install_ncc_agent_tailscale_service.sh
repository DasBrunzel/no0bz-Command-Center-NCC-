#!/usr/bin/env sh
set -eu
exec "$(dirname "$0")/install_ncc_agent_service.sh" --tailscale "$@"
