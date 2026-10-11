#!/usr/bin/env bash
# Build a source-checkout-free Linux bootstrap archive on any x86_64 Linux
# build host.  It deliberately embeds only a public verification key.
set -euo pipefail

KEY_ID=''
PUBLIC_KEY=''
VERSION='0.6.0-beta.4'
OUTPUT_DIRECTORY=''
CORE_BINARY=''
BUILD_CORE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --key-id) KEY_ID="$2"; shift 2 ;;
    --public-key) PUBLIC_KEY="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --output-directory) OUTPUT_DIRECTORY="$2"; shift 2 ;;
    --core-binary) CORE_BINARY="$2"; shift 2 ;;
    --build-core) BUILD_CORE=1; shift ;;
    *) echo "usage: $0 --key-id ID --public-key BASE64 [--version VERSION] [--core-binary PATH] [--build-core] [--output-directory PATH]" >&2; exit 2 ;;
  esac
done
[[ -n "$KEY_ID" && "$KEY_ID" =~ ^[A-Za-z0-9._-]{1,64}$ ]] || { echo 'A valid --key-id is required.' >&2; exit 2; }
[[ -n "$PUBLIC_KEY" ]] || { echo '--public-key is required.' >&2; exit 2; }
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]] || { echo 'Invalid semantic version.' >&2; exit 2; }
[[ "$(printf '%s' "$PUBLIC_KEY" | base64 -d 2>/dev/null | wc -c)" -eq 32 ]] || { echo 'Public key must be a 32-byte Base64 Ed25519 key.' >&2; exit 2; }

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIRECTORY="${OUTPUT_DIRECTORY:-$PROJECT/dist/bootstrap}"
CORE_BINARY="${CORE_BINARY:-$PROJECT/core/ncc-core/target/release/ncc-core}"
if (( BUILD_CORE )); then
  command -v cargo >/dev/null || { echo 'cargo is required for --build-core.' >&2; exit 1; }
  cargo build --release --manifest-path "$PROJECT/core/ncc-core/Cargo.toml"
fi
[[ -x "$CORE_BINARY" ]] || { echo "Linux Core binary missing or not executable: $CORE_BINARY" >&2; exit 1; }
command -v tar >/dev/null || { echo 'tar is required.' >&2; exit 1; }

work="$(mktemp -d)"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$OUTPUT_DIRECTORY"
install -m 0755 "$CORE_BINARY" "$work/ncc-core"
install -m 0755 "$PROJECT/scripts/install_ncc_core_linux_bootstrap.sh" "$work/install_ncc_core_linux_bootstrap.sh"
install -m 0755 "$PROJECT/scripts/rollback_ncc_core_to_agent.sh" "$work/rollback_ncc_core_to_agent.sh"
install -m 0644 "$PROJECT/packaging/systemd/ncc-core.service" "$work/ncc-core.service"
printf '{"keys":{"%s":"%s"}}\n' "$KEY_ID" "$PUBLIC_KEY" >"$work/trusted-keys.json"
cat >"$work/README.md" <<EOF
# NCC Core Linux Bootstrap $VERSION

1. Assign an approved signed **Linux x86_64** release to the existing device in
   the NCC dashboard.
2. Extract this archive completely.
3. Run: \`sudo ./install_ncc_core_linux_bootstrap.sh\`

The existing 0.5 agent remains untouched unless Core becomes healthy. After a
successful health check it is retired, with its configuration retained as a
rollback backup.
EOF
archive="$OUTPUT_DIRECTORY/ncc-core-bootstrap-$VERSION-linux-x86_64.tar.gz"
tar -C "$work" -czf "$archive" .
printf '{"result":"NCC Core Linux bootstrap package built","package":"%s","sha256":"%s"}\n' \
  "$archive" "$(sha256sum "$archive" | awk '{print $1}')"
