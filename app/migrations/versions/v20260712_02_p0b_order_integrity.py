from __future__ import annotations

VERSION = "20260712_02_p0b_order_integrity"


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
        order_additions = {
            "idempotency_key": "ALTER TABLE orders ADD COLUMN idempotency_key VARCHAR(128)",
            "request_hash": "ALTER TABLE orders ADD COLUMN request_hash CHAR(64)",
            "reservation_expires_at": "ALTER TABLE orders ADD COLUMN reservation_expires_at VARCHAR(40)",
        }
        for column, statement in order_additions.items():
            if column not in order_columns:
                connection.execute(statement)

        material_columns = _mysql_columns(connection, database, "managed_materials")
        if "reserved_stock" not in material_columns:
            connection.execute(
                "ALTER TABLE managed_materials ADD COLUMN reserved_stock INT NOT NULL DEFAULT 0"
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS order_requests (
              user_id VARCHAR(100) NOT NULL,
              idempotency_key VARCHAR(128) NOT NULL,
              request_hash CHAR(64) NOT NULL,
              order_id VARCHAR(80),
              status VARCHAR(20) NOT NULL DEFAULT 'processing',
              created_at VARCHAR(40) NOT NULL,
              updated_at VARCHAR(40) NOT NULL,
              PRIMARY KEY (user_id, idempotency_key),
              UNIQUE KEY ux_order_requests_order (order_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_reservations (
              reservation_id VARCHAR(80) PRIMARY KEY,
              order_id VARCHAR(80) NOT NULL,
              sku_id VARCHAR(160) NOT NULL,
              sku_code VARCHAR(160) NOT NULL DEFAULT '',
              quantity INT NOT NULL,
              status VARCHAR(20) NOT NULL DEFAULT 'reserved',
              expires_at VARCHAR(40) NOT NULL,
              created_at VARCHAR(40) NOT NULL,
              updated_at VARCHAR(40) NOT NULL,
              confirmed_at VARCHAR(40),
              released_at VARCHAR(40),
              UNIQUE KEY ux_inventory_reservation_order_sku (order_id, sku_id),
              INDEX idx_inventory_reservations_expiry (status, expires_at),
              INDEX idx_inventory_reservations_sku (sku_id, status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        indexes = _mysql_indexes(connection, database, "orders")
        if "ux_orders_user_idempotency" not in indexes:
            connection.execute(
                "CREATE UNIQUE INDEX ux_orders_user_idempotency ON orders(user_id, idempotency_key)"
            )
        return

    order_columns = _sqlite_columns(connection, "orders")
    order_additions = {
        "idempotency_key": "ALTER TABLE orders ADD COLUMN idempotency_key TEXT",
        "request_hash": "ALTER TABLE orders ADD COLUMN request_hash TEXT",
        "reservation_expires_at": "ALTER TABLE orders ADD COLUMN reservation_expires_at TEXT",
    }
    for column, statement in order_additions.items():
        if column not in order_columns:
            connection.execute(statement)

    material_columns = _sqlite_columns(connection, "managed_materials")
    if "reserved_stock" not in material_columns:
        connection.execute(
            "ALTER TABLE managed_materials ADD COLUMN reserved_stock INTEGER NOT NULL DEFAULT 0"
        )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS order_requests (
          user_id TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          order_id TEXT,
          status TEXT NOT NULL DEFAULT 'processing',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (user_id, idempotency_key),
          UNIQUE (order_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_reservations (
          reservation_id TEXT PRIMARY KEY,
          order_id TEXT NOT NULL,
          sku_id TEXT NOT NULL,
          sku_code TEXT NOT NULL DEFAULT '',
          quantity INTEGER NOT NULL CHECK (quantity > 0),
          status TEXT NOT NULL DEFAULT 'reserved',
          expires_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT,
          released_at TEXT,
          UNIQUE (order_id, sku_id)
        )
        """
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_user_idempotency "
        "ON orders(user_id, idempotency_key)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_reservations_expiry "
        "ON inventory_reservations(status, expires_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_reservations_sku "
        "ON inventory_reservations(sku_id, status)"
    )


def downgrade(connection, backend: str, database: str = "") -> None:
    if backend == "mysql":
        indexes = _mysql_indexes(connection, database, "orders")
        if "ux_orders_user_idempotency" in indexes:
            connection.execute("DROP INDEX ux_orders_user_idempotency ON orders")
        connection.execute("DROP TABLE IF EXISTS inventory_reservations")
        connection.execute("DROP TABLE IF EXISTS order_requests")
        material_columns = _mysql_columns(connection, database, "managed_materials")
        if "reserved_stock" in material_columns:
            connection.execute("ALTER TABLE managed_materials DROP COLUMN reserved_stock")
        order_columns = _mysql_columns(connection, database, "orders")
        for column in ("reservation_expires_at", "request_hash", "idempotency_key"):
            if column in order_columns:
                connection.execute(f"ALTER TABLE orders DROP COLUMN {column}")
        return

    connection.execute("DROP INDEX IF EXISTS idx_inventory_reservations_sku")
    connection.execute("DROP INDEX IF EXISTS idx_inventory_reservations_expiry")
    connection.execute("DROP INDEX IF EXISTS ux_orders_user_idempotency")
    connection.execute("DROP TABLE IF EXISTS inventory_reservations")
    connection.execute("DROP TABLE IF EXISTS order_requests")
    material_columns = _sqlite_columns(connection, "managed_materials")
    if "reserved_stock" in material_columns:
        connection.execute("ALTER TABLE managed_materials DROP COLUMN reserved_stock")
    order_columns = _sqlite_columns(connection, "orders")
    for column in ("reservation_expires_at", "request_hash", "idempotency_key"):
        if column in order_columns:
            connection.execute(f"ALTER TABLE orders DROP COLUMN {column}")
