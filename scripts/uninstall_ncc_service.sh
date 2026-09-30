#!/usr/bin/env sh
set -eu

[ "$(id -u)" -eq 0 ] || { echo "[FEHLER] Bitte mit sudo starten." >&2; exit 1; }
component=${1:-}
[ "$component" = agent ] || [ "$component" = server ] || { echo "Aufruf: $0 {agent|server} [--purge]" >&2; exit 2; }
purge=${2:-}
unit="ncc-$component.service"
systemctl disable --now "$unit" 2>/dev/null || true
rm -f "/etc/systemd/system/$unit"
systemctl daemon-reload
if [ "$purge" = "--purge" ]; then
  rm -f "/etc/ncc/$component.env"
  if [ "$component" = agent ]; then rm -rf /var/lib/ncc-agent; fi
  echo "[NCC] Dienst und $component-Daten wurden entfernt."
else
  echo "[NCC] Dienst entfernt; Konfiguration und Daten bleiben erhalten."
fi
