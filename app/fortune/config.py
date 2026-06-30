from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parents[1] / "data"


@lru_cache(maxsize=16)
def load_config(filename: str) -> dict[str, Any]:
    path = CONFIG_DIR / filename
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
