#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python_cmd=python3
[ -x .venv/bin/python ] && python_cmd=.venv/bin/python
tailscale_ip=$($python_cmd scripts/tailscale_ip.py) || {
  echo "[FEHLER] Keine aktive Tailscale-IP gefunden." >&2
  exit 1
}
if ! "$python_cmd" scripts/ncc_token.py check >/dev/null 2>&1; then
  "$python_cmd" scripts/ncc_token.py generate --export ncc-token-transfer.txt
fi
export NCC_MODE=server
export NCC_HOST="$tailscale_ip"
echo "[NCC] TAILSCALE-SERVER: http://$NCC_HOST:8350"
echo "[NCC] Nur die Tailscale-Schnittstelle wird gebunden."
exec scripts/start_ncc.sh
