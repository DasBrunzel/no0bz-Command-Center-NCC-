from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

def main() -> None:
    import uvicorn
    from ncc.config import get_settings

    settings = get_settings()
    if settings.host not in {"127.0.0.1", "::1", "localhost"}:
        logging.warning("NCC is exposed beyond loopback. Use HTTPS via a trusted reverse proxy.")
    uvicorn.run("ncc.app:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()

