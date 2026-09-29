#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python_cmd=python3
[ -x .venv/bin/python ] && python_cmd=.venv/bin/python
echo "NCC Token Manager"
echo "  generate              Token erstmalig erzeugen"
echo "  show                  Token anzeigen"
echo "  rotate                Token rotieren und exportieren"
echo "  export [datei]        Token exportieren"
echo "  import [datei]        Token-Datei importieren"
action=${1:-show}
case "$action" in
  generate) "$python_cmd" scripts/ncc_token.py generate ;;
  show) "$python_cmd" scripts/ncc_token.py show ;;
  rotate) "$python_cmd" scripts/ncc_token.py generate --force --export "${2:-ncc-token-transfer.txt}" ;;
  export) "$python_cmd" scripts/ncc_token.py export "${2:-ncc-token-transfer.txt}" ;;
  import) "$python_cmd" scripts/ncc_token.py import-file "${2:?Pfad zur Token-Datei fehlt}" ;;
  *) echo "Unbekannte Aktion: $action" >&2; exit 2 ;;
esac
