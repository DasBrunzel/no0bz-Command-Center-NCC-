#!/usr/bin/env bash
# Promote an already healthy Core payload without deleting or rewriting the
# legacy agent configuration.  The companion rollback script restores 0.5.
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo 'Run through sudo.' >&2; exit 1; }

root=/var/lib/ncc-core
core=/opt/no0bz/ncc/core/ncc-core
agent_env=/etc/ncc/agent.env
core_env=/etc/ncc/core.env
[[ -x "$core" && -f "$agent_env" && -f "$core_env" ]] || { echo 'NCC Core or agent configuration is missing.' >&2; exit 1; }

before="$($core --state-dir "$root" status)"
if ! grep -q '"active_payload":"' <<<"$before" || ! grep -q '"health":"healthy"' <<<"$before"; then
  echo "NccCore payload is not healthy; no changes made: $before" >&2
  exit 1
fi

backup="/etc/ncc/core.env.before-primary-switch-$(date +%Y%m%d-%H%M%S).bak"
cp --preserve=mode,ownership "$core_env" "$backup"
{
  printf 'NCC_CORE_STATE_DIR=%s\n' "$root"
  grep '^NCC_AGENT_[A-Z0-9_]*=' "$agent_env"
} >"$core_env"
chown root:ncc "$core_env"
chmod 0640 "$core_env"

systemctl stop ncc-core.service || true
systemctl stop ncc-agent.service
systemctl disable ncc-agent.service
if ! systemctl start ncc-core.service; then
  systemctl enable --now ncc-agent.service
  echo 'Core could not start; ncc-agent was restored.' >&2
  exit 1
fi
sleep 5
after="$($core --state-dir "$root" status)"
if ! systemctl is-active --quiet ncc-core.service || ! grep -q '"health":"healthy"' <<<"$after"; then
  systemctl stop ncc-core.service || true
  systemctl enable --now ncc-agent.service
  echo "Core failed its health gate; ncc-agent was restored: $after" >&2
  exit 1
fi
printf '{"result":"NccCore promoted; ncc-agent disabled as fallback","state":%s,"backup":"%s","rollback":"%s"}\n' "$after" "$backup" "$(dirname "$0")/rollback_ncc_core_to_agent.sh"
