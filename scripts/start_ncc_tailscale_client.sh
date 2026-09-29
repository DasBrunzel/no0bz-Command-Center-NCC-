#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python_cmd=python3
[ -x .venv/bin/python ] && python_cmd=.venv/bin/python
target=${1:-}
if [ -z "$target" ]; then
  printf "Tailscale-IP oder MagicDNS-Name des Servers: "
  read -r target
fi
if [ -z "$target" ]; then
  echo "[FEHLER] Serveradresse fehlt." >&2
  exit 1
fi
if ! "$python_cmd" scripts/ncc_token.py check >/dev/null 2>&1; then
  token_file=${2:-}
  if [ -z "$token_file" ]; then
    printf "Pfad zur Übergabedatei: "
    read -r token_file
  fi
  "$python_cmd" scripts/ncc_token.py import-file "$token_file"
fi
export NCC_MODE=client
export NCC_HOST=127.0.0.1
export NCC_SERVER_URL="http://$target:8350"
export NCC_TOKEN=$($python_cmd scripts/ncc_token.py value)
echo "[NCC] TAILSCALE-CLIENT - sende an $NCC_SERVER_URL"
exec scripts/start_ncc.sh
