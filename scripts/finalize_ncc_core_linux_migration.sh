#!/usr/bin/env bash
# Retire the legacy Linux 0.5 agent only after the already-installed NCC Core
# has proved healthy. The 0.5 configuration is archived, never deleted.
set -euo pipefail

EXPECTED_VERSION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --expected-version) EXPECTED_VERSION="$2"; shift 2 ;;
    *) echo "usage: $0 [--expected-version VERSION]" >&2; exit 2 ;;
  esac
done

[[ ${EUID} -eq 0 ]] || { echo 'Run through sudo.' >&2; exit 1; }

CORE_SERVICE=ncc-core.service
LEGACY_SERVICE=ncc-agent.service
CORE_BINARY=/opt/no0bz/ncc/core/ncc-core
CORE_ROOT=/var/lib/ncc-core
AGENT_ENV=/etc/ncc/agent.env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -x "$CORE_BINARY" ]] || { echo "NCC Core binary missing: $CORE_BINARY" >&2; exit 1; }
[[ -f "$AGENT_ENV" ]] || {
  echo 'Legacy agent configuration is already archived or unavailable; no change made.' >&2
  exit 1
}

core_status() {
  runuser -u ncc -- "$CORE_BINARY" --state-dir "$CORE_ROOT" status
}

is_healthy() {
  local state="$1"
  systemctl is-active --quiet "$CORE_SERVICE" &&
    grep -q '"health":"healthy"' <<<"$state" &&
    grep -q '"active_payload":"' <<<"$state" &&
    { [[ -z "$EXPECTED_VERSION" ]] || grep -q "\"active_payload\":\"$EXPECTED_VERSION\"" <<<"$state"; }
}

before="$(core_status 2>/dev/null || true)"
if ! is_healthy "$before"; then
  echo "NCC Core is not healthy with the expected payload. Legacy agent remains active. State: $before" >&2
  exit 1
fi

backup="/etc/ncc/agent.env.retired-$(date +%Y%m%d-%H%M%S).bak"
mv "$AGENT_ENV" "$backup"

if ! systemctl disable --now "$LEGACY_SERVICE"; then
  cp --preserve=mode,ownership "$backup" "$AGENT_ENV"
  systemctl enable --now "$LEGACY_SERVICE" || true
  echo 'Could not stop/disable the legacy agent; it was restored.' >&2
  exit 1
fi

sleep 6
after="$(core_status 2>/dev/null || true)"
if ! is_healthy "$after"; then
  cp --preserve=mode,ownership "$backup" "$AGENT_ENV"
  systemctl enable --now "$LEGACY_SERVICE" || true
  echo "NCC Core failed the post-retirement health check; legacy agent restored. State: $after" >&2
  exit 1
fi

printf '{"result":"legacy ncc-agent retired","core_state":%s,"legacy_config_backup":"%s","rollback":"sudo %s"}\n' \
  "$after" "$backup" "$SCRIPT_DIR/rollback_ncc_core_to_agent.sh"
