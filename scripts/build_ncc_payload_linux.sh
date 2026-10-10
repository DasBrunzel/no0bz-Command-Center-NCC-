#!/usr/bin/env bash
# Build the Linux x86_64 NCC telemetry payload.  Signing is intentionally a
# separate Windows step so the encrypted private release key never leaves
# HorstPC.
set -euo pipefail

VERSION=''
OUTPUT_DIRECTORY=''
PYTHON_BIN="${PYTHON_BIN:-python3}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --output-directory) OUTPUT_DIRECTORY="$2"; shift 2 ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    *) echo "usage: $0 --version VERSION [--python PYTHON] [--output-directory PATH]" >&2; exit 2 ;;
  esac
done
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]] || { echo 'A semantic --version is required.' >&2; exit 2; }
command -v "$PYTHON_BIN" >/dev/null || { echo "Python not found: $PYTHON_BIN" >&2; exit 1; }
"$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1 || {
  echo "PyInstaller is missing for $PYTHON_BIN. Install it in an isolated build venv first." >&2; exit 1;
}

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIRECTORY="${OUTPUT_DIRECTORY:-$PROJECT/dist/payloads}"
work="$(mktemp -d)"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$OUTPUT_DIRECTORY" "$work/content"

"$PYTHON_BIN" -m PyInstaller --noconfirm --clean --onefile --name ncc-payload \
  --paths "$PROJECT/backend" \
  --collect-submodules ncc --collect-submodules ncc_agent --collect-submodules ncc_payload \
  --distpath "$work/dist" --workpath "$work/build" --specpath "$work" \
  "$PROJECT/backend/ncc_payload/__main__.py"

install -m 0755 "$work/dist/ncc-payload" "$work/content/ncc-payload"
printf '{"executable":"ncc-payload","arguments":[]}\n' > "$work/content/payload.json"
archive="$OUTPUT_DIRECTORY/ncc-payload-$VERSION-linux-x86_64.zip"
rm -f "$archive"
(cd "$work/content" && zip -q -9 "$archive" ncc-payload payload.json)
printf '{"result":"Unsigned NCC Linux payload built","artifact":"%s","sha256":"%s","size_bytes":%s}\n' \
  "$archive" "$(sha256sum "$archive" | awk '{print $1}')" "$(stat -c%s "$archive")"
