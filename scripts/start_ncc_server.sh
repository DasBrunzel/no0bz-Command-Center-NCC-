#!/usr/bin/env sh
set -eu
export NCC_MODE=server
export NCC_HOST=0.0.0.0
echo "[NCC] SERVER-Modus - Dashboard und Node-API laufen auf Port 8350."
echo "[NCC] Clients benötigen die LAN-IP dieses PCs und denselben NCC_TOKEN."
exec "$(dirname "$0")/start_ncc.sh"
