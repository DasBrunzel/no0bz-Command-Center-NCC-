#!/usr/bin/env bash
# Install an Ed25519 public key only. The private signing key stays on the
# release workstation, never on a server or monitored device.
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then echo 'Run through sudo.' >&2; exit 1; fi
if [[ $# -ne 2 || ! $1 =~ ^[A-Za-z0-9._-]{1,64}$ ]]; then
  echo "usage: $0 KEY_ID BASE64_ED25519_PUBLIC_KEY" >&2; exit 2
fi
key_id="$1"; public_key="$2"
if ! printf '%s' "$public_key" | base64 -d 2>/dev/null | wc -c | grep -qx '32'; then
  echo 'The public key must be a 32 byte Ed25519 key encoded as Base64.' >&2; exit 1
fi
config=/var/lib/ncc-core/config
path="$config/trusted-keys.json"
install -d -o ncc -g ncc -m 0750 "$config"
KEY_ID="$key_id" PUBLIC_KEY="$public_key" TARGET="$path" python3 - <<'PY'
import json, os
from pathlib import Path

target = Path(os.environ["TARGET"])
keys = {}
if target.exists():
    keys = json.loads(target.read_text(encoding="utf-8")).get("keys", {})
if not isinstance(keys, dict):
    raise SystemExit("existing trusted key file is invalid")
keys[os.environ["KEY_ID"]] = os.environ["PUBLIC_KEY"]
target.write_text(json.dumps({"keys": keys}, separators=(",", ":")), encoding="utf-8")
PY
chown ncc:ncc "$path"
chmod 0640 "$path"
printf '{"result":"public release key installed","key_id":"%s","path":"%s"}\n' "$key_id" "$path"
