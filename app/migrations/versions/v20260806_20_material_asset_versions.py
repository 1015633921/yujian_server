from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


VERSION = "20260806_20_material_asset_versions"


def _columns(connection, backend: str, database: str) -> set[str]:
    if backend == "mysql":
        return {
            str(row["COLUMN_NAME"])
            for row in connection.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=? AND TABLE_NAME='material_taxonomy'",
                (database,),
            ).fetchall()
        }
    return {str(row["name"]) for row in connection.execute("PRAGMA table_info(material_taxonomy)").fetchall()}


def upgrade(connection, backend: str, database: str = "") -> None:
    """Add optimistic-concurrency and audit storage for gallery publishing."""
    if "asset_version" not in _columns(connection, backend, database):
        column_type = "INT NOT NULL DEFAULT 1" if backend == "mysql" else "INTEGER NOT NULL DEFAULT 1"
        connection.execute(f"ALTER TABLE material_taxonomy ADD COLUMN asset_version {column_type}")
    if backend == "mysql":
        suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS material_asset_versions (
                version_id VARCHAR(80) PRIMARY KEY,
                series_id VARCHAR(120) NOT NULL,
                asset_version INT NOT NULL,
                image_url VARCHAR(2000) NOT NULL DEFAULT '',
                image_urls_json LONGTEXT NOT NULL,
                source VARCHAR(40) NOT NULL DEFAULT 'gallery_publish',
                actor_id VARCHAR(80) NOT NULL DEFAULT '',
                created_at VARCHAR(40) NOT NULL,
                UNIQUE KEY uq_material_asset_versions_series_version (series_id, asset_version),
                INDEX idx_material_asset_versions_series_created (series_id, created_at)
            )
            """ + suffix
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS material_asset_publish_requests (
                idempotency_key VARCHAR(120) PRIMARY KEY,
                series_id VARCHAR(120) NOT NULL,
                response_json LONGTEXT NOT NULL,
                created_at VARCHAR(40) NOT NULL,
                INDEX idx_material_asset_publish_requests_series (series_id)
            )
            """ + suffix
        )
    else:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS material_asset_versions (
                version_id TEXT PRIMARY KEY,
                series_id TEXT NOT NULL,
                asset_version INTEGER NOT NULL,
                image_url TEXT NOT NULL DEFAULT '',
                image_urls_json TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'gallery_publish',
                actor_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(series_id, asset_version)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_material_asset_versions_series_created "
            "ON material_asset_versions (series_id, created_at)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS material_asset_publish_requests (
                idempotency_key TEXT PRIMARY KEY,
                series_id TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_material_asset_publish_requests_series "
            "ON material_asset_publish_requests (series_id)"
        )

    # Preserve the pre-migration visual state as V1, so the first gallery
    # publish always has a recoverable before-image rather than starting at V2.
    rows = connection.execute(
        """
        SELECT item_id, asset_version, image_url, image_urls_json, updated_at
        FROM material_taxonomy s
        WHERE kind='series'
          AND NOT EXISTS (
            SELECT 1 FROM material_asset_versions v
            WHERE v.series_id=s.item_id AND v.asset_version=s.asset_version
          )
        """
    ).fetchall()
    now = datetime.now(UTC).isoformat()
    for row in rows:
        item = dict(row)
        connection.execute(
            """
            INSERT INTO material_asset_versions
            (version_id, series_id, asset_version, image_url, image_urls_json, source, actor_id, created_at)
            VALUES (?, ?, ?, ?, ?, 'migration_snapshot', '', ?)
            """,
            (
                f"matasset_{uuid4().hex}",
                item["item_id"],
                max(1, int(item.get("asset_version") or 1)),
                item.get("image_url") or "",
                item.get("image_urls_json") or "[]",
                item.get("updated_at") or now,
            ),
        )


def downgrade(connection, backend: str, database: str = "") -> None:
    """Retain audit data; previous releases safely ignore the additive schema."""
    return None
