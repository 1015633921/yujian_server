from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import pymysql

TABLES = [
    "energy_assessments",
    "daily_energies",
    "daily_checkins",
    "users",
    "admin_users",
    "admin_sessions",
    "admin_login_logs",
    "managed_materials",
    "content_blocks",
    "community_posts",
    "recommendation_plans",
    "orders",
    "diy_designs",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default="/app/data/yujian_fastapi.db")
    parser.add_argument("--database", required=True)
    args = parser.parse_args()

    os.environ["DATABASE_BACKEND"] = "mysql"
    os.environ["MYSQL_DATABASE"] = args.database
    from app.database import ensure_mysql_schema

    ensure_mysql_schema()
    source = sqlite3.connect(Path(args.sqlite))
    source.row_factory = sqlite3.Row
    target = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=args.database,
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with target.cursor() as cursor:
            for table in reversed(TABLES):
                cursor.execute(f"TRUNCATE TABLE `{table}`")
            for table in TABLES:
                exists = source.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if not exists:
                    print(f"{table}: skipped (missing in sqlite)")
                    continue
                rows = source.execute(f'SELECT * FROM "{table}"').fetchall()
                if not rows:
                    print(f"{table}: 0")
                    continue
                columns = rows[0].keys()
                column_sql = ", ".join(f"`{name}`" for name in columns)
                placeholders = ", ".join(["%s"] * len(columns))
                cursor.executemany(
                    f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders})",
                    [tuple(row[name] for name in columns) for row in rows],
                )
                print(f"{table}: {len(rows)}")
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    main()
