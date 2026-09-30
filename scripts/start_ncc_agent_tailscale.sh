#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
target=${1:-}
if [ -z "$target" ]; then
  printf "Tailscale-IP oder MagicDNS-Name des Servers: "
  read -r target
fi
if [ -z "$target" ]; then
  echo "[FEHLER] Tailscale-Adresse fehlt." >&2
  exit 1
fi
server_url=$(python3 -m scripts.ncc_connection normalize "$target")
export NCC_AGENT_SERVER_URL="$server_url"
export NCC_AGENT_ALLOW_INSECURE_HTTP=1
exec scripts/start_ncc_agent.sh
