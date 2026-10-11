#!/usr/bin/env bash
# NCC Core bootstrap for an existing Linux 0.5 agent.
# The legacy service is retired only after an assigned signed payload is
# running healthy.  Its configuration is archived rather than discarded so
# rollback remains possible.
set -euo pipefail

KEEP_LEGACY=0
HEALTH_TIMEOUT=75
while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-legacy-agent) KEEP_LEGACY=1; shift ;;
    --health-timeout-seconds) HEALTH_TIMEOUT="$2"; shift 2 ;;
    *) echo "usage: $0 [--keep-legacy-agent] [--health-timeout-seconds 20..180]" >&2; exit 2 ;;
  esac
done
[[ $EUID -eq 0 ]] || { echo 'Run this bootstrap through sudo.' >&2; exit 1; }
[[ "$HEALTH_TIMEOUT" =~ ^[0-9]+$ && "$HEALTH_TIMEOUT" -ge 20 && "$HEALTH_TIMEOUT" -le 180 ]] || {
  echo 'Health timeout must be between 20 and 180 seconds.' >&2; exit 2;
}

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_SOURCE="$PACKAGE_ROOT/ncc-core"
KEYS_SOURCE="$PACKAGE_ROOT/trusted-keys.json"
SERVICE_SOURCE="$PACKAGE_ROOT/ncc-core.service"
AGENT_ENV=/etc/ncc/agent.env
CORE_ROOT=/var/lib/ncc-core
CORE_ENV=/etc/ncc/core.env
CORE_BINARY=/opt/no0bz/ncc/core/ncc-core
CORE_AGENT_DATA_DIR="$CORE_ROOT/agent-data"

for path in "$CORE_SOURCE" "$KEYS_SOURCE" "$SERVICE_SOURCE" "$AGENT_ENV"; do
  [[ -f "$path" ]] || { echo "Required bootstrap file missing: $path" >&2; exit 1; }
done
[[ -x "$CORE_SOURCE" ]] || { echo "Bootstrap Core is not executable: $CORE_SOURCE" >&2; exit 1; }

read_agent_value() {
  python3 - "$AGENT_ENV" "$1" <<'PY'
import re
import sys
from pathlib import Path

name = sys.argv[2]
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    match = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
    if match and match.group(1) == name:
        print(match.group(2).strip().strip('"').strip("'"))
        break
PY
}

data_dir="$(read_agent_value NCC_AGENT_DATA_DIR)"
data_dir="${data_dir:-/var/lib/ncc-agent}"
credential_file="$data_dir/agent-credential.json"
agent_token="$(python3 - "$credential_file" <<'PY'
import json
import sys
from pathlib import Path

try:
    token = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("token", "")
except (OSError, ValueError, TypeError):
    token = ""
if not isinstance(token, str) or not token:
    raise SystemExit(1)
print(token)
PY
)" || {
  echo "Existing NCC browser credential is missing or invalid: $credential_file" >&2
  echo 'The existing ncc-agent remains unchanged.' >&2
  exit 1
}

id ncc >/dev/null 2>&1 || useradd --system --home /var/lib/ncc-core --shell /usr/sbin/nologin ncc
install -d -o ncc -g ncc -m 0750 /opt/no0bz/ncc/core "$CORE_ROOT"/{state,config,payloads,downloads}
# The legacy service can run under root while Core deliberately runs as the
# unprivileged ncc account.  Give Core a private state directory, but seed the
# stable machine identity and credential so both implementations represent the
# same node during migration.  Never modify the legacy agent's live files.
install -d -o ncc -g ncc -m 0700 "$CORE_AGENT_DATA_DIR"
for state_file in machine-id agent-credential.json; do
  source_file="$data_dir/$state_file"
  target_file="$CORE_AGENT_DATA_DIR/$state_file"
  if [[ -f "$source_file" && ! -e "$target_file" ]]; then
    install -o ncc -g ncc -m 0600 "$source_file" "$target_file"
  fi
done
# Core runs as the unprivileged ncc account and reads core.env through the
# directory. Keep the directory root-owned but make it searchable for ncc;
# core.env itself remains root-owned and group-readable only.
install -d -o root -g ncc -m 0750 /etc/ncc
install -o root -g root -m 0755 "$CORE_SOURCE" "$CORE_BINARY"
install -o ncc -g ncc -m 0640 "$KEYS_SOURCE" "$CORE_ROOT/config/trusted-keys.json"
install -o root -g root -m 0644 "$SERVICE_SOURCE" /etc/systemd/system/ncc-core.service

{
  echo "NCC_CORE_STATE_DIR=$CORE_ROOT"
  printf 'NCC_AGENT_TOKEN=%s\n' "$agent_token"
  echo "NCC_AGENT_DATA_DIR=$CORE_AGENT_DATA_DIR"
  grep '^NCC_AGENT_[A-Z0-9_]*=' "$AGENT_ENV" | grep -v -E '^NCC_AGENT_(TOKEN|DATA_DIR)=' || true
} >"$CORE_ENV"
chown root:ncc "$CORE_ENV"
chmod 0640 "$CORE_ENV"

systemctl daemon-reload
systemctl enable ncc-core.service
systemctl stop ncc-core.service || true

as_core() {
  runuser --preserve-environment -u ncc -- bash -c 'set -a; . /etc/ncc/core.env; set +a; exec "$@"' -- "$@"
}

update_output="$(as_core "$CORE_BINARY" --state-dir "$CORE_ROOT" check-update 2>&1)" || {
  echo "Could not check the approved NCC release: $update_output" >&2
  echo 'The existing ncc-agent remains unchanged.' >&2
  exit 1
}
state_before="$(as_core "$CORE_BINARY" --state-dir "$CORE_ROOT" status)"
if ! grep -q '"active_payload":"' <<<"$state_before"; then
  echo 'No approved NCC Linux release is assigned to this device yet.' >&2
  echo 'The existing ncc-agent remains unchanged; assign the Linux release in the Dashboard and run this bootstrap again.' >&2
  exit 1
fi

systemctl start ncc-core.service
deadline=$((SECONDS + HEALTH_TIMEOUT))
state=''
while (( SECONDS < deadline )); do
  sleep 2
  state="$(as_core "$CORE_BINARY" --state-dir "$CORE_ROOT" status 2>/dev/null || true)"
  if systemctl is-active --quiet ncc-core.service && grep -q '"health":"healthy"' <<<"$state"; then
    break
  fi
done

if ! systemctl is-active --quiet ncc-core.service || ! grep -q '"health":"healthy"' <<<"$state"; then
  systemctl stop ncc-core.service || true
  systemctl enable --now ncc-agent.service || true
  echo "NccCore did not become healthy. The legacy agent was restored. Last state: $state" >&2
  exit 1
fi

if (( KEEP_LEGACY )); then
  printf '{"result":"NccCore installed and healthy; legacy ncc-agent retained by request","state":%s}\n' "$state"
  exit 0
fi

backup="/etc/ncc/agent.env.retired-$(date +%Y%m%d-%H%M%S).bak"
systemctl stop ncc-agent.service || true
systemctl disable ncc-agent.service || true
mv "$AGENT_ENV" "$backup"
printf '{"result":"NccCore installed, healthy, and legacy ncc-agent retired","state":%s,"legacy_config_backup":"%s","rollback":"%s"}\n' \
  "$state" "$backup" "$PACKAGE_ROOT/rollback_ncc_core_to_agent.sh"
