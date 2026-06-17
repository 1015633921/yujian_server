from __future__ import annotations

import traceback
import sys
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "local-api.out.log"

sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    try:
        with LOG_FILE.open("a", encoding="utf-8") as log:
            log.write("starting local api via .venv_codex\n")
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
