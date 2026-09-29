#!/usr/bin/env sh
set -eu
export NCC_MODE=client
export NCC_HOST=127.0.0.1
server_url=${NCC_SERVER_URL:-${1:-}}
if [ -z "$server_url" ]; then
  printf "Server-URL (z.B. http://192.168.1.10:8350): "
  read -r server_url
fi
if [ -z "$server_url" ]; then
  echo "[FEHLER] Eine Server-URL ist erforderlich." >&2
  exit 1
fi
token=${NCC_TOKEN:-${2:-}}
if [ -z "$token" ]; then
  printf "NCC_TOKEN des Servers: "
  stty -echo
  read -r token
  stty echo
  printf "\n"
fi
if [ -z "$token" ]; then
  echo "[FEHLER] Der gemeinsame Server-Token ist erforderlich." >&2
  exit 1
fi
export NCC_SERVER_URL="$server_url"
export NCC_TOKEN="$token"
echo "[NCC] CLIENT-Modus - sende Telemetrie an $NCC_SERVER_URL."
exec "$(dirname "$0")/start_ncc.sh"
