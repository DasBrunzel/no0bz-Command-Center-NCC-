from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "dist"
TARGET = ROOT / "backend" / "ncc" / "static"


def main() -> None:
    if not SOURCE.is_dir():
        raise SystemExit("frontend/dist fehlt; zuerst im Ordner frontend `npm run build` ausführen")
    shutil.rmtree(TARGET, ignore_errors=True)
    shutil.copytree(SOURCE, TARGET)
    print(f"Frontend copied to {TARGET}")


if __name__ == "__main__":
    main()

