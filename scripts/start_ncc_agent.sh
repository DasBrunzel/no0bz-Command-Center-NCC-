#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
test -d .venv || python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
server_url=${NCC_AGENT_SERVER_URL:-${1:-}}
if [ -z "$server_url" ]; then
  printf "NCC Server-URL (HTTPS oder Tailscale): "
  read -r server_url
fi
if [ -z "$server_url" ]; then
  echo "[FEHLER] Eine Server-URL ist erforderlich." >&2
  exit 1
fi
token=${NCC_AGENT_TOKEN:-${2:-}}
if [ -z "$token" ]; then
  printf "Individueller Agent-Token: "
  stty -echo
  read -r token
  stty echo
  printf "\n"
fi
if [ -z "$token" ]; then
  echo "[FEHLER] Ein individueller Agent-Token ist erforderlich." >&2
  exit 1
fi
export NCC_AGENT_SERVER_URL="$server_url"
export NCC_AGENT_TOKEN="$token"
export PYTHONPATH=backend
echo "[NCC] Starte den GUI-losen Agenten fuer $NCC_AGENT_SERVER_URL."
exec python -m ncc_agent.main
