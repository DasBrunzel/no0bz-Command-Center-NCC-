#!/usr/bin/env sh
set -eu
component=${1:-all}
case "$component" in
  agent|server) units="ncc-$component.service" ;;
  all) units="ncc-agent.service ncc-server.service" ;;
  *) echo "Aufruf: $0 {agent|server|all}" >&2; exit 2 ;;
esac
for unit in $units; do
  printf '\n=== %s ===\n' "$unit"
  systemctl status "$unit" --no-pager 2>/dev/null || true
  journalctl -u "$unit" -n 40 --no-pager 2>/dev/null || true
done
