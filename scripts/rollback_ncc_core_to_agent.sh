#!/usr/bin/env bash
# Safe local fallback for switch_ncc_core_to_primary.sh.  No payload, pairing,
# token, telemetry buffer, or configuration file is deleted.
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo 'Run through sudo.' >&2; exit 1; }
systemctl stop ncc-core.service || true
if [[ ! -f /etc/ncc/agent.env ]]; then
  latest_backup="$(find /etc/ncc -maxdepth 1 -type f -name 'agent.env.retired-*.bak' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)"
  [[ -n "$latest_backup" && -f "$latest_backup" ]] || {
    echo 'Legacy agent configuration is unavailable; rollback stopped safely.' >&2
    exit 1
  }
  cp --preserve=mode,ownership "$latest_backup" /etc/ncc/agent.env
fi
systemctl enable --now ncc-agent.service
systemctl is-active --quiet ncc-agent.service
printf '%s\n' '{"result":"legacy ncc-agent restored; ncc-core stopped"}'
