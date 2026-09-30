#!/usr/bin/env sh
set -eu
exec "$(dirname "$0")/install_ncc_server_service.sh" --tailscale "$@"
