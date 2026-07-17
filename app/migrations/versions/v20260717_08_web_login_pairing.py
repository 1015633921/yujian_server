from __future__ import annotations


VERSION = "20260717_08_web_login_pairing"


def upgrade(connection, backend: str, database: str = "") -> None:
    del database
    if backend == "mysql":
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS web_login_pairings (
              id VARCHAR(80) PRIMARY KEY,
              browser_secret_hash CHAR(64) NOT NULL UNIQUE,
              verification_code_hash CHAR(64) NOT NULL,
              status VARCHAR(20) NOT NULL,
              confirmed_user_id VARCHAR(100),
              confirmed_session_id VARCHAR(80),
              failed_confirm_attempts INT NOT NULL DEFAULT 0,
              created_at VARCHAR(40) NOT NULL,
              expires_at VARCHAR(40) NOT NULL,
              confirmed_at VARCHAR(40),
              consumed_at VARCHAR(40),
              INDEX idx_web_login_pairings_status_expiry (status, expires_at),
              INDEX idx_web_login_pairings_confirmed_user (confirmed_user_id, confirmed_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        return

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS web_login_pairings (
          id TEXT PRIMARY KEY,
          browser_secret_hash TEXT NOT NULL UNIQUE,
          verification_code_hash TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'consumed', 'expired')),
          confirmed_user_id TEXT,
          confirmed_session_id TEXT,
          failed_confirm_attempts INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          confirmed_at TEXT,
          consumed_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_login_pairings_status_expiry
        ON web_login_pairings(status, expires_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_login_pairings_confirmed_user
        ON web_login_pairings(confirmed_user_id, confirmed_at)
        """
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    del backend, database
    connection.execute("DROP TABLE IF EXISTS web_login_pairings")
