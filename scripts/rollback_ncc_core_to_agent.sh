#!/usr/bin/env bash
# Safe local fallback for switch_ncc_core_to_primary.sh.  No payload, pairing,
# token, telemetry buffer, or configuration file is deleted.
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo 'Run through sudo.' >&2; exit 1; }
systemctl stop ncc-core.service || true
systemctl enable --now ncc-agent.service
systemctl is-active --quiet ncc-agent.service
printf '%s\n' '{"result":"legacy ncc-agent restored; ncc-core stopped"}'
