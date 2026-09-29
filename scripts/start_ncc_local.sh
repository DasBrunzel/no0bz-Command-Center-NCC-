#!/usr/bin/env sh
set -eu
export NCC_MODE=local
export NCC_HOST=127.0.0.1
exec "$(dirname "$0")/start_ncc.sh"
