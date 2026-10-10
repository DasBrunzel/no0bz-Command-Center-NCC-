#!/usr/bin/env bash
# Controlled Linux equivalent of the Windows Core test migration.  It never
# changes ncc-agent.service or /etc/ncc/agent.env; the Core is tested with its
# own tiny, signed local payload.
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo 'Run this script through sudo.' >&2
  exit 1
fi

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_MANIFEST="$PROJECT/core/ncc-core/Cargo.toml"
CORE_BINARY="$PROJECT/core/ncc-core/target/release/ncc-core"
INSTALLER="$PROJECT/scripts/install_ncc_core_service.sh"
STATE_ROOT=/var/lib/ncc-core
CORE_ENV=/etc/ncc/core.env

while [[ $# -gt 0 ]]; do
  case "$1" in
    --core-binary) CORE_BINARY="$2"; shift 2 ;;
    *) echo "usage: $0 [--core-binary /path/to/ncc-core]" >&2; exit 2 ;;
  esac
done

command -v openssl >/dev/null || { echo 'OpenSSL is required to sign the test payload.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Python 3 is required to package the test payload.' >&2; exit 1; }
[[ -f /etc/ncc/agent.env ]] || { echo 'Existing agent configuration missing: /etc/ncc/agent.env' >&2; exit 1; }

if [[ ! -x "$CORE_BINARY" ]]; then
  command -v cargo >/dev/null || { echo 'Rust/Cargo is required to build the test Core.' >&2; exit 1; }
  cargo build --release --manifest-path "$CORE_MANIFEST"
fi
[[ -x "$CORE_BINARY" ]] || { echo "Core binary missing after build: $CORE_BINARY" >&2; exit 1; }
"$INSTALLER" --core-binary "$CORE_BINARY" --agent-env /etc/ncc/agent.env
systemctl stop ncc-core.service || true

work="$(mktemp -d /tmp/ncc-core-linux-test.XXXXXX)"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT

version='0.6.0-beta.linux-test'
payload_dir="$work/payload"
mkdir -p "$payload_dir"
cat >"$payload_dir/test-payload" <<'PAYLOAD'
#!/usr/bin/env sh
set -eu
: "${NCC_CORE_STATE_DIR:?missing NCC_CORE_STATE_DIR}"
mkdir -p "$NCC_CORE_STATE_DIR"
printf '{"payload_version":"%s","status":"ready"}\n' "${NCC_TEST_PAYLOAD_VERSION:?missing payload version}" > "$NCC_CORE_STATE_DIR/payload-health.json"
while :; do sleep 60; done
PAYLOAD
chmod 0755 "$payload_dir/test-payload"
printf '%s\n' '{"executable":"test-payload","arguments":[]}' > "$payload_dir/payload.json"
PAYLOAD_DIR="$payload_dir" ARCHIVE="$work/payload.zip" python3 - <<'PY'
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

payload = Path(os.environ["PAYLOAD_DIR"])
with ZipFile(os.environ["ARCHIVE"], "w", ZIP_DEFLATED) as archive:
    for name in ("test-payload", "payload.json"):
        archive.write(payload / name, name)
PY

sha="$(sha256sum "$work/payload.zip" | awk '{print $1}')"
size="$(stat -c '%s' "$work/payload.zip")"
# The Core deliberately stages as the unprivileged `ncc` user.  Make only this
# throw-away, signed test archive readable while keeping the temporary signing
# key root-only.
chown ncc:ncc "$work/payload.zip"
chmod 0644 "$work/payload.zip"
chmod 0755 "$work"
printf 'NCC-AGENT-RELEASE-V1\n%s\n%s\n%s\n' "$version" "$sha" "$size" > "$work/statement.txt"
openssl genpkey -algorithm ED25519 -out "$work/private.pem" >/dev/null 2>&1
openssl pkey -in "$work/private.pem" -pubout -outform DER -out "$work/public.der" >/dev/null 2>&1
openssl pkeyutl -sign -rawin -inkey "$work/private.pem" -in "$work/statement.txt" -out "$work/signature.bin"
public="$(tail -c 32 "$work/public.der" | base64 -w0)"
signature="$(base64 -w0 "$work/signature.bin")"

install -d -o ncc -g ncc -m 0750 "$STATE_ROOT/config"
printf '{"keys":{"temporary-linux-migration-test":"%s"}}\n' "$public" > "$STATE_ROOT/config/trusted-keys.json"
chown ncc:ncc "$STATE_ROOT/config/trusted-keys.json"
chmod 0640 "$STATE_ROOT/config/trusted-keys.json"

# Stage as the same unprivileged account used by ncc-core.service.  Otherwise
# root would own the activated files and the service could neither execute the
# payload nor read its health record.
as_core() {
  runuser --preserve-environment -u ncc -- bash -c 'set -a; . /etc/ncc/core.env; set +a; exec "$@"' -- "$@"
}

as_core /opt/no0bz/ncc/core/ncc-core --state-dir "$STATE_ROOT" stage --source "$work/payload.zip" --version "$version" --sha256 "$sha" --size "$size" --key-id temporary-linux-migration-test --signature "$signature"
as_core /opt/no0bz/ncc/core/ncc-core --state-dir "$STATE_ROOT" activate --version "$version"
systemctl start ncc-core.service
sleep 3
state="$(as_core /opt/no0bz/ncc/core/ncc-core --state-dir "$STATE_ROOT" status)"
systemctl is-active --quiet ncc-core.service
grep -q '"healthy"' <<<"$state"
echo '[NCC] Linux Core test migration healthy; existing 0.5 ncc-agent remains unchanged.'
echo "$state"
