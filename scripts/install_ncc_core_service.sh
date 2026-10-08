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

# Keep only the variables the payload needs. Credentials remain root/ncc readable
# and no updater ever rewrites the original agent.env.
{ echo 'NCC_CORE_STATE_DIR=/var/lib/ncc-core'; grep '^NCC_AGENT_[A-Z0-9_]*=' "$AGENT_ENV"; } >/etc/ncc/core.env
chown root:ncc /etc/ncc/core.env
chmod 0640 /etc/ncc/core.env
install -o root -g root -m 0644 "$(dirname "$0")/../packaging/systemd/ncc-core.service" /etc/systemd/system/ncc-core.service
systemctl daemon-reload
systemctl enable ncc-core.service
echo 'NccCore installed but intentionally not started. Stage and activate a signed payload first.'
