from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    static = ROOT / "backend" / "ncc" / "static"
    if not static.joinpath("index.html").exists():
        raise SystemExit("Built frontend missing; run the frontend build first")
    separator = ";" if sys.platform == "win32" else ":"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name",
            "ncc",
            "--onefile",
            "--add-data",
            f"{static}{separator}ncc/static",
            "main.py",
        ],
        cwd=ROOT,
        check=True,
        shell=False,
        timeout=1800,
    )


if __name__ == "__main__":
    main()

