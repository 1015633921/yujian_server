from __future__ import annotations

import sys
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
SITE_PACKAGES = ROOT / ".venv" / "Lib" / "site-packages"
LOG_FILE = ROOT / "local-api.runner.log"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SITE_PACKAGES))

import uvicorn  # noqa: E402


if __name__ == "__main__":
    try:
        with LOG_FILE.open("a", encoding="utf-8") as log:
            log.write("starting local api\n")
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_config=None,
        )
    except Exception:
        with LOG_FILE.open("a", encoding="utf-8") as log:
            log.write(traceback.format_exc())
        raise
