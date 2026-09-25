#!/usr/bin/env python3
"""Launch the Dexibo web UI with uvicorn."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is importable when run as a script
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> None:
    import uvicorn

    host = os.getenv("DEXIBO_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("DEXIBO_WEB_PORT", "8787"))
    print(f"Dexibo web → http://{host}:{port}", flush=True)
    uvicorn.run(
        "dexibo.webapp:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
