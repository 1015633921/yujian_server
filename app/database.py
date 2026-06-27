from __future__ import annotations

import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = BASE_DIR / "data" / "yujian_fastapi.db"

_schema_lock = threading.Lock()
_schema_ready: set[str] = set()


def use_mysql() -> bool:
    return os.getenv("DATABASE_BACKEND", "sqlite").lower() == "mysql"


def integrity_errors():
    if not use_mysql():
        return (sqlite3.IntegrityError,)
    import pymysql

    return (pymysql.IntegrityError,)


class MySQLConnection:
    def __init__(self):
        import pymysql

        self.raw = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "mysql"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=os.environ["MYSQL_DATABASE"],
            charset="utf8mb4",
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=15,
            write_timeout=15,
        )

    @staticmethod
    def _sql(sql: str, params: Any) -> str:
        if isinstance(params, dict):
            return re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)
        return sql.replace("?", "%s")

    def execute(self, sql: str, params: Any = ()):
        cursor = self.raw.cursor()
        cursor.execute(self._sql(sql, params), params)
        return cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.raw.commit()
        else:
            self.raw.rollback()
        self.raw.close()


def connect_database(db_path: Path | str | None = None):
    if db_path is not None or not use_mysql():
        path = Path(db_path or DEFAULT_SQLITE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection
    ensure_mysql_schema()
    return MySQLConnection()


MYSQL_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS energy_assessments (
      assessment_id VARCHAR(80) PRIMARY KEY, user_id VARCHAR(100), fingerprint VARCHAR(128) NOT NULL,
      name VARCHAR(100) NOT NULL, core_wish VARCHAR(255) NOT NULL, result_json LONGTEXT NOT NULL,
      created_at VARCHAR(40) NOT NULL, INDEX idx_energy_assessments_user_created (user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_energies (
      user_id VARCHAR(100) NOT NULL, energy_date VARCHAR(20) NOT NULL, mode VARCHAR(40) NOT NULL,
      assessment_id VARCHAR(80), result_json LONGTEXT NOT NULL, created_at VARCHAR(40) NOT NULL,
      updated_at VARCHAR(40) NOT NULL, PRIMARY KEY (user_id, energy_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_checkins (
      user_id VARCHAR(100) NOT NULL, checkin_date VARCHAR(20) NOT NULL, mood INT NOT NULL,
      sleep INT NOT NULL, stress INT NOT NULL, created_at VARCHAR(40) NOT NULL,
      updated_at VARCHAR(40) NOT NULL, PRIMARY KEY (user_id, checkin_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
      user_id VARCHAR(100) PRIMARY KEY, openid VARCHAR(100), unionid VARCHAR(100),
      nickname VARCHAR(100), avatar_url VARCHAR(1000), gender VARCHAR(20), phone_number VARCHAR(32),
      source VARCHAR(40) NOT NULL, created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
      INDEX idx_users_openid (openid)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS system_settings (
      setting_key VARCHAR(120) PRIMARY KEY,
      setting_json LONGTEXT NOT NULL,
      updated_at VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_users (
      admin_id VARCHAR(80) PRIMARY KEY, username VARCHAR(100) NOT NULL UNIQUE,
      password_hash VARCHAR(255) NOT NULL, salt VARCHAR(100) NOT NULL, role VARCHAR(40) NOT NULL,
      display_name VARCHAR(120), status VARCHAR(20) NOT NULL DEFAULT 'active',
      failed_login_count INT NOT NULL DEFAULT 0, locked_until VARCHAR(40),
      last_login_at VARCHAR(40), last_login_ip VARCHAR(80),
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_sessions (
      token VARCHAR(255) PRIMARY KEY, admin_id VARCHAR(80) NOT NULL,
      expires_at VARCHAR(40) NOT NULL, created_at VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_login_logs (
      log_id VARCHAR(80) PRIMARY KEY, admin_id VARCHAR(80), username VARCHAR(100) NOT NULL,
      success TINYINT NOT NULL DEFAULT 0, reason VARCHAR(80) NOT NULL,
      ip VARCHAR(80), user_agent VARCHAR(500), created_at VARCHAR(40) NOT NULL,
      INDEX idx_admin_login_logs_created (created_at),
      INDEX idx_admin_login_logs_username (username, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS managed_materials (
      id VARCHAR(160) PRIMARY KEY, skuId VARCHAR(160) NOT NULL, top VARCHAR(40) NOT NULL,
      category VARCHAR(100) NOT NULL, series VARCHAR(160) NOT NULL DEFAULT '',
      grade VARCHAR(40) NOT NULL DEFAULT '', name VARCHAR(160) NOT NULL, effect VARCHAR(255) NOT NULL,
      element VARCHAR(20) NOT NULL, price DOUBLE NOT NULL, size DOUBLE NOT NULL, weight DOUBLE NOT NULL,
      color VARCHAR(40) NOT NULL, shine VARCHAR(40) NOT NULL, image_path VARCHAR(1000),
      image_url VARCHAR(2000), image_urls_json LONGTEXT, stock INT NOT NULL DEFAULT 0, enabled TINYINT NOT NULL DEFAULT 1, sort_order INT NOT NULL DEFAULT 0,
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS content_blocks (
      block_id VARCHAR(100) PRIMARY KEY, section VARCHAR(80) NOT NULL, title VARCHAR(255) NOT NULL,
      subtitle TEXT, body LONGTEXT, image_url VARCHAR(2000), action_text VARCHAR(255),
      action_url VARCHAR(1000), status VARCHAR(40) NOT NULL, sort_order INT NOT NULL DEFAULT 0,
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS home_banners (
      banner_id VARCHAR(100) PRIMARY KEY, title VARCHAR(255) NOT NULL, subtitle TEXT,
      eyebrow VARCHAR(255), image_url VARCHAR(2000), action_text VARCHAR(255),
      action_url VARCHAR(1000), theme VARCHAR(40) NOT NULL DEFAULT 'dark',
      status VARCHAR(40) NOT NULL, sort_order INT NOT NULL DEFAULT 0,
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
      INDEX idx_home_banners_status_sort (status, sort_order, updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS community_posts (
      post_id VARCHAR(100) PRIMARY KEY, title VARCHAR(255) NOT NULL, author VARCHAR(120) NOT NULL,
      description TEXT, story LONGTEXT, scene VARCHAR(255), author_note TEXT, likes INT NOT NULL DEFAULT 0,
      tone VARCHAR(40), recipe_json LONGTEXT NOT NULL, materials_json LONGTEXT NOT NULL, tags_json LONGTEXT NOT NULL,
      image_url VARCHAR(2000), is_home_hot TINYINT NOT NULL DEFAULT 0,
      status VARCHAR(40) NOT NULL, sort_order INT NOT NULL DEFAULT 0,
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
      INDEX idx_community_posts_status_sort (status, sort_order, updated_at),
      INDEX idx_community_posts_home_hot (status, is_home_hot, sort_order, updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS recommendation_plans (
      plan_id VARCHAR(100) PRIMARY KEY, name VARCHAR(255) NOT NULL, subtitle TEXT, description TEXT,
      price DOUBLE NOT NULL DEFAULT 0, tone VARCHAR(40), recipe_json LONGTEXT NOT NULL,
      materials_json LONGTEXT NOT NULL, design_story LONGTEXT, design_reason LONGTEXT,
      scenes_json LONGTEXT NOT NULL, tags_json LONGTEXT NOT NULL, image_url VARCHAR(2000),
      is_home_hot TINYINT NOT NULL DEFAULT 1, status VARCHAR(40) NOT NULL, sort_order INT NOT NULL DEFAULT 0,
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
      INDEX idx_recommendation_plans_status_sort (status, is_home_hot, sort_order, updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
      order_id VARCHAR(40) PRIMARY KEY, out_trade_no VARCHAR(40) NOT NULL UNIQUE,
      user_id VARCHAR(100) NOT NULL, openid VARCHAR(100), status VARCHAR(40) NOT NULL,
      payment_status VARCHAR(40) NOT NULL, total_amount DOUBLE NOT NULL, total_fee INT NOT NULL,
      currency VARCHAR(20) NOT NULL, receiver_json LONGTEXT NOT NULL, design_json LONGTEXT NOT NULL,
      sequence_json LONGTEXT NOT NULL, bom_json LONGTEXT NOT NULL, remark TEXT, payment_json LONGTEXT,
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL, paid_at VARCHAR(40),
      after_sale_status VARCHAR(40), refund_status VARCHAR(40), logistics_json LONGTEXT,
      status_history_json LONGTEXT, design_id VARCHAR(80), refund_json LONGTEXT,
      INDEX idx_orders_user_created (user_id, created_at),
      INDEX idx_orders_status (status, payment_status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS diy_designs (
      design_id VARCHAR(80) PRIMARY KEY, user_id VARCHAR(100) NOT NULL, status VARCHAR(40) NOT NULL,
      design_json LONGTEXT NOT NULL, sequence_json LONGTEXT NOT NULL, order_id VARCHAR(40),
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
      INDEX idx_diy_designs_user_updated (user_id, updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS cart_items (
      cart_item_id VARCHAR(80) PRIMARY KEY, user_id VARCHAR(100) NOT NULL,
      item_type VARCHAR(40) NOT NULL, item_id VARCHAR(100), item_json LONGTEXT NOT NULL,
      quantity INT NOT NULL DEFAULT 1, created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
      INDEX idx_cart_items_user_updated (user_id, updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS user_addresses (
      address_id VARCHAR(80) PRIMARY KEY, user_id VARCHAR(100) NOT NULL,
      name VARCHAR(100) NOT NULL, phone VARCHAR(32) NOT NULL,
      region_json LONGTEXT NOT NULL, detail_address VARCHAR(500) NOT NULL,
      address VARCHAR(800) NOT NULL, is_default TINYINT NOT NULL DEFAULT 0,
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
      INDEX idx_user_addresses_user_updated (user_id, updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS user_coupons (
      coupon_id VARCHAR(80) PRIMARY KEY, user_id VARCHAR(100) NOT NULL,
      title VARCHAR(160) NOT NULL, coupon_type VARCHAR(40) NOT NULL DEFAULT 'amount',
      value DOUBLE NOT NULL DEFAULT 0, min_amount DOUBLE NOT NULL DEFAULT 0,
      status VARCHAR(40) NOT NULL DEFAULT 'unused', expires_at VARCHAR(40),
      created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
      INDEX idx_user_coupons_user_status (user_id, status, expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def ensure_mysql_schema() -> None:
    if not use_mysql():
        return
    database = os.environ["MYSQL_DATABASE"]
    if database in _schema_ready:
        return
    with _schema_lock:
        if database in _schema_ready:
            return
        connection = MySQLConnection()
        try:
            for statement in MYSQL_SCHEMA:
                connection.execute(statement)
            ensure_mysql_columns(connection)
            connection.raw.commit()
            _schema_ready.add(database)
        finally:
            connection.raw.close()


def ensure_mysql_columns(connection: MySQLConnection) -> None:
    database = os.environ["MYSQL_DATABASE"]
    migrations = {
        "orders": {
            "refund_json": "ALTER TABLE orders ADD COLUMN refund_json LONGTEXT",
        },
        "managed_materials": {
            "image_urls_json": "ALTER TABLE managed_materials ADD COLUMN image_urls_json LONGTEXT",
        },
        "community_posts": {
            "is_home_hot": "ALTER TABLE community_posts ADD COLUMN is_home_hot TINYINT NOT NULL DEFAULT 0",
        }
    }
    for table, columns in migrations.items():
        existing = {
            row["COLUMN_NAME"]
            for row in connection.execute(
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                """,
                (database, table),
            ).fetchall()
        }
        for column, sql in columns.items():
            if column not in existing:
                connection.execute(sql)
