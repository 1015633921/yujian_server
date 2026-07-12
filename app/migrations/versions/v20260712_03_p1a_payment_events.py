from __future__ import annotations

VERSION = "20260712_03_p1a_payment_events"


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
        order_columns = _mysql_columns(connection, database, "orders")
        additions = {
            "payment_provider": "ALTER TABLE orders ADD COLUMN payment_provider VARCHAR(32)",
            "payment_transaction_id": "ALTER TABLE orders ADD COLUMN payment_transaction_id VARCHAR(160)",
            "payment_appid": "ALTER TABLE orders ADD COLUMN payment_appid VARCHAR(100)",
            "payment_mchid": "ALTER TABLE orders ADD COLUMN payment_mchid VARCHAR(100)",
            "payment_currency": "ALTER TABLE orders ADD COLUMN payment_currency VARCHAR(20)",
            "payment_confirmed_at": "ALTER TABLE orders ADD COLUMN payment_confirmed_at VARCHAR(40)",
        }
        for column, statement in additions.items():
            if column not in order_columns:
                connection.execute(statement)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_webhook_events (
              id VARCHAR(80) PRIMARY KEY,
              provider VARCHAR(32) NOT NULL,
              provider_event_id VARCHAR(160) NOT NULL,
              event_type VARCHAR(80) NOT NULL,
              resource_id VARCHAR(160) NOT NULL DEFAULT '',
              transaction_id VARCHAR(160) NOT NULL DEFAULT '',
              merchant_order_no VARCHAR(80) NOT NULL DEFAULT '',
              payload_hash CHAR(64) NOT NULL,
              received_at VARCHAR(40) NOT NULL,
              processed_at VARCHAR(40),
              processing_status VARCHAR(32) NOT NULL DEFAULT 'received',
              failure_reason VARCHAR(120) NOT NULL DEFAULT '',
              conflict_count INT NOT NULL DEFAULT 0,
              security_alert_at VARCHAR(40),
              created_at VARCHAR(40) NOT NULL,
              updated_at VARCHAR(40) NOT NULL,
              UNIQUE KEY ux_payment_webhook_provider_event (provider, provider_event_id),
              INDEX idx_payment_webhook_order_received (merchant_order_no, received_at),
              INDEX idx_payment_webhook_status_updated (processing_status, updated_at),
              INDEX idx_payment_webhook_transaction (provider, transaction_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        indexes = _mysql_indexes(connection, database, "orders")
        if "ux_orders_payment_provider_transaction" not in indexes:
            connection.execute(
                "CREATE UNIQUE INDEX ux_orders_payment_provider_transaction "
                "ON orders(payment_provider, payment_transaction_id)"
            )
        return

    order_columns = _sqlite_columns(connection, "orders")
    additions = {
        "payment_provider": "ALTER TABLE orders ADD COLUMN payment_provider TEXT",
        "payment_transaction_id": "ALTER TABLE orders ADD COLUMN payment_transaction_id TEXT",
        "payment_appid": "ALTER TABLE orders ADD COLUMN payment_appid TEXT",
        "payment_mchid": "ALTER TABLE orders ADD COLUMN payment_mchid TEXT",
        "payment_currency": "ALTER TABLE orders ADD COLUMN payment_currency TEXT",
        "payment_confirmed_at": "ALTER TABLE orders ADD COLUMN payment_confirmed_at TEXT",
    }
    for column, statement in additions.items():
        if column not in order_columns:
            connection.execute(statement)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_webhook_events (
          id TEXT PRIMARY KEY,
          provider TEXT NOT NULL,
          provider_event_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          resource_id TEXT NOT NULL DEFAULT '',
          transaction_id TEXT NOT NULL DEFAULT '',
          merchant_order_no TEXT NOT NULL DEFAULT '',
          payload_hash TEXT NOT NULL,
          received_at TEXT NOT NULL,
          processed_at TEXT,
          processing_status TEXT NOT NULL DEFAULT 'received',
          failure_reason TEXT NOT NULL DEFAULT '',
          conflict_count INTEGER NOT NULL DEFAULT 0,
          security_alert_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_webhook_provider_event "
        "ON payment_webhook_events(provider, provider_event_id)"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_payment_provider_transaction "
        "ON orders(payment_provider, payment_transaction_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_webhook_order_received "
        "ON payment_webhook_events(merchant_order_no, received_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_webhook_status_updated "
        "ON payment_webhook_events(processing_status, updated_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_payment_webhook_transaction "
        "ON payment_webhook_events(provider, transaction_id)"
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        indexes = _mysql_indexes(connection, database, "orders")
        if "ux_orders_payment_provider_transaction" in indexes:
            connection.execute("DROP INDEX ux_orders_payment_provider_transaction ON orders")
        connection.execute("DROP TABLE IF EXISTS payment_webhook_events")
        order_columns = _mysql_columns(connection, database, "orders")
        for column in (
            "payment_confirmed_at",
            "payment_currency",
            "payment_mchid",
            "payment_appid",
            "payment_transaction_id",
            "payment_provider",
        ):
            if column in order_columns:
                connection.execute(f"ALTER TABLE orders DROP COLUMN {column}")
        return

    connection.execute("DROP INDEX IF EXISTS idx_payment_webhook_transaction")
    connection.execute("DROP INDEX IF EXISTS idx_payment_webhook_status_updated")
    connection.execute("DROP INDEX IF EXISTS idx_payment_webhook_order_received")
    connection.execute("DROP INDEX IF EXISTS ux_payment_webhook_provider_event")
    connection.execute("DROP INDEX IF EXISTS ux_orders_payment_provider_transaction")
    connection.execute("DROP TABLE IF EXISTS payment_webhook_events")
    order_columns = _sqlite_columns(connection, "orders")
    for column in (
        "payment_confirmed_at",
        "payment_currency",
        "payment_mchid",
        "payment_appid",
        "payment_transaction_id",
        "payment_provider",
    ):
        if column in order_columns:
            connection.execute(f"ALTER TABLE orders DROP COLUMN {column}")
