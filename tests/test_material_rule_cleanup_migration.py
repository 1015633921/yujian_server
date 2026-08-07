from __future__ import annotations

import sqlite3

from app.migrations.versions import v20260807_24_material_rule_cleanup as migration


def _columns(connection: sqlite3.Connection) -> set[str]:
    return {str(row["name"]) for row in connection.execute("PRAGMA table_info(material_knowledge)").fetchall()}


def test_material_rule_cleanup_drops_and_restores_legacy_conflict_column(tmp_path):
    connection = sqlite3.connect(tmp_path / "material-rule-cleanup.db")
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            """
            CREATE TABLE material_knowledge (
                code TEXT PRIMARY KEY,
                allowed_roles_json TEXT NOT NULL,
                conflict_codes_json TEXT NOT NULL,
                match_rules_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO material_knowledge VALUES ('bead_a', '[\"primary\"]', '[\"bead_b\"]', '[\"no_limit\"]')"
        )

        migration.upgrade(connection, "sqlite")

        assert "conflict_codes_json" not in _columns(connection)
        assert connection.execute("SELECT code FROM material_knowledge").fetchone()["code"] == "bead_a"

        migration.downgrade(connection, "sqlite")

        assert "conflict_codes_json" in _columns(connection)
        assert connection.execute("SELECT conflict_codes_json FROM material_knowledge").fetchone()[0] == "[]"
    finally:
        connection.close()
