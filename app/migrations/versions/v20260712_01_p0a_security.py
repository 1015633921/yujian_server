from __future__ import annotations

VERSION = "20260712_01_p0a_security"


def _sqlite_columns(connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def _mysql_columns(connection, database: str, table: str) -> set[str]:
    rows = connection.execute(
        """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        """,
        (database, table),
    ).fetchall()
    return {row["COLUMN_NAME"] for row in rows}


def _mysql_indexes(connection, database: str, table: str) -> set[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        """,
        (database, table),
    ).fetchall()
    return {row["INDEX_NAME"] for row in rows}


def upgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
              id VARCHAR(80) PRIMARY KEY,
              user_id VARCHAR(100) NOT NULL,
              token_hash CHAR(64) NOT NULL UNIQUE,
              created_at VARCHAR(40) NOT NULL,
              expires_at VARCHAR(40) NOT NULL,
              revoked_at VARCHAR(40),
              last_seen_at VARCHAR(40),
              INDEX idx_user_sessions_user_active (user_id, revoked_at, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        columns = _mysql_columns(connection, database, "diy_designs")
        additions = {
            "share_status": "ALTER TABLE diy_designs ADD COLUMN share_status VARCHAR(20) NOT NULL DEFAULT 'private'",
            "share_token_hash": "ALTER TABLE diy_designs ADD COLUMN share_token_hash CHAR(64)",
            "share_published_at": "ALTER TABLE diy_designs ADD COLUMN share_published_at VARCHAR(40)",
            "share_revoked_at": "ALTER TABLE diy_designs ADD COLUMN share_revoked_at VARCHAR(40)",
        }
        for column, statement in additions.items():
            if column not in columns:
                connection.execute(statement)
        if "ux_diy_designs_share_token_hash" not in _mysql_indexes(connection, database, "diy_designs"):
            connection.execute(
                "CREATE UNIQUE INDEX ux_diy_designs_share_token_hash ON diy_designs(share_token_hash)"
            )
        return

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
          id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          token_hash TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          revoked_at TEXT,
          last_seen_at TEXT
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_sessions_user_active "
        "ON user_sessions(user_id, revoked_at, expires_at)"
    )
    columns = _sqlite_columns(connection, "diy_designs")
    additions = {
        "share_status": "ALTER TABLE diy_designs ADD COLUMN share_status TEXT NOT NULL DEFAULT 'private'",
        "share_token_hash": "ALTER TABLE diy_designs ADD COLUMN share_token_hash TEXT",
        "share_published_at": "ALTER TABLE diy_designs ADD COLUMN share_published_at TEXT",
        "share_revoked_at": "ALTER TABLE diy_designs ADD COLUMN share_revoked_at TEXT",
    }
    for column, statement in additions.items():
        if column not in columns:
            connection.execute(statement)
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_diy_designs_share_token_hash "
        "ON diy_designs(share_token_hash)"
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        indexes = _mysql_indexes(connection, database, "diy_designs")
        if "ux_diy_designs_share_token_hash" in indexes:
            connection.execute("DROP INDEX ux_diy_designs_share_token_hash ON diy_designs")
        columns = _mysql_columns(connection, database, "diy_designs")
        for column in ("share_revoked_at", "share_published_at", "share_token_hash", "share_status"):
            if column in columns:
                connection.execute(f"ALTER TABLE diy_designs DROP COLUMN {column}")
        connection.execute("DROP TABLE IF EXISTS user_sessions")
        return

    connection.execute("DROP INDEX IF EXISTS ux_diy_designs_share_token_hash")
    columns = _sqlite_columns(connection, "diy_designs")
    for column in ("share_revoked_at", "share_published_at", "share_token_hash", "share_status"):
        if column in columns:
            connection.execute(f"ALTER TABLE diy_designs DROP COLUMN {column}")
    connection.execute("DROP TABLE IF EXISTS user_sessions")
