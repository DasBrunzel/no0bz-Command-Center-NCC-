#!/usr/bin/env bash
set -euo pipefail

# Installs only the small Core service. It keeps the existing ncc-agent.service
# untouched so a payload can be tested in parallel and rolled back safely.
CORE_BINARY=""
AGENT_ENV="/etc/ncc/agent.env"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --core-binary) CORE_BINARY="$2"; shift 2 ;;
    --agent-env) AGENT_ENV="$2"; shift 2 ;;
    *) echo "usage: $0 --core-binary /path/to/ncc-core [--agent-env /etc/ncc/agent.env]" >&2; exit 2 ;;
  esac
done
[[ $EUID -eq 0 ]] || { echo "run as root (sudo)" >&2; exit 1; }
[[ -n "$CORE_BINARY" && -x "$CORE_BINARY" ]] || { echo "--core-binary must be an executable file" >&2; exit 1; }
[[ -f "$AGENT_ENV" ]] || { echo "agent environment missing: $AGENT_ENV" >&2; exit 1; }

id ncc >/dev/null 2>&1 || useradd --system --home /var/lib/ncc-core --shell /usr/sbin/nologin ncc
install -d -o ncc -g ncc -m 0750 /opt/no0bz/ncc/core /var/lib/ncc-core/{state,config,payloads} /var/lib/ncc-agent /etc/ncc
install -o root -g root -m 0755 "$CORE_BINARY" /opt/no0bz/ncc/core/ncc-core

# Browser-paired 0.5 agents keep their bearer credential in the protected
# agent data directory rather than in agent.env.  The Core needs that same
# credential only for the authenticated release lookup.  Do not print it.
agent_data_dir="$(python3 - "$AGENT_ENV" <<'PY'
import re
import sys
from pathlib import Path

values = {}
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    match = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
    if match:
        values[match.group(1)] = match.group(2).strip().strip('"').strip("'")
print(values.get("NCC_AGENT_DATA_DIR", "/var/lib/ncc-agent"))
PY
)"
credential_file="$agent_data_dir/agent-credential.json"
agent_token="$(python3 - "$credential_file" <<'PY'
import json
import sys
from pathlib import Path

try:
    value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("token", "")
except (OSError, ValueError, TypeError):
    value = ""
if not isinstance(value, str) or not value:
    raise SystemExit(1)
print(value)
PY
)" || {
  echo "Existing NCC agent credential is missing or invalid: $credential_file" >&2
  exit 1
}

# Keep the original agent configuration untouched.  The separate Core
# environment is root/ncc readable; no token is written to stdout.
{
  echo 'NCC_CORE_STATE_DIR=/var/lib/ncc-core'
  printf 'NCC_AGENT_TOKEN=%s\n' "$agent_token"
  grep '^NCC_AGENT_[A-Z0-9_]*=' "$AGENT_ENV" | grep -v '^NCC_AGENT_TOKEN=' || true
} >/etc/ncc/core.env
chown root:ncc /etc/ncc/core.env
chmod 0640 /etc/ncc/core.env
install -o root -g root -m 0644 "$(dirname "$0")/../packaging/systemd/ncc-core.service" /etc/systemd/system/ncc-core.service
systemctl daemon-reload
systemctl enable ncc-core.service
echo 'NccCore installed but intentionally not started. Stage and activate a signed payload first.'
