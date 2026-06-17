from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.admin_service import AdminService
from app.bead_catalog import ensure_official_bead_catalog
from app.repository import DB_PATH


def main() -> None:
    AdminService()
    with sqlite3.connect(DB_PATH) as connection:
        inserted = ensure_official_bead_catalog(connection)
        total = connection.execute(
            "SELECT COUNT(*) FROM managed_materials WHERE top = 'bead'"
        ).fetchone()[0]
    print(f"official bead catalog imported: inserted={inserted}, total_beads={total}, db={DB_PATH}")


if __name__ == "__main__":
    main()
