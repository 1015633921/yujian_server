from __future__ import annotations

import sqlite3

from app.admin_service import AdminService
from app.migrations.runner import downgrade, upgrade
from app.migrations.versions.v20260717_09_community_ugc_core import TABLES, VERSION
from app.order_service import OrderService
from app.repository import AssessmentRepository
from app.runtime_health import database_readiness


def sqlite_tables(path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def sqlite_indexes(path, table: str) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA index_list({table})")}


def test_community_migration_is_explicit_idempotent_and_reversible(tmp_path, monkeypatch):
    db_path = tmp_path / "community-migration.db"
    AssessmentRepository(db_path)
    OrderService(db_path)
    AdminService(db_path)

    applied = upgrade("sqlite", db_path)
    assert applied[-1] == VERSION
    assert upgrade("sqlite", db_path) == []
    assert set(TABLES).issubset(sqlite_tables(db_path))
    assert "community_posts" in sqlite_tables(db_path)
    assert "idx_ugc_posts_design" in sqlite_indexes(db_path, "community_ugc_posts")

    monkeypatch.setenv("COMMUNITY_UGC_ENABLED", "true")
    assert database_readiness(db_path)["ok"] is True

    assert downgrade("sqlite", db_path, steps=1) == [VERSION]
    assert not set(TABLES).intersection(sqlite_tables(db_path))
    assert "community_posts" in sqlite_tables(db_path)
    assert database_readiness(db_path)["ok"] is False

    assert upgrade("sqlite", db_path) == [VERSION]
    assert set(TABLES).issubset(sqlite_tables(db_path))
    assert "idx_ugc_posts_design" in sqlite_indexes(db_path, "community_ugc_posts")
