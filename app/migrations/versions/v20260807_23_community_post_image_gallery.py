from __future__ import annotations

import json


VERSION = "20260807_23_community_post_image_gallery"
ROLLBACK_PLAN = (
    "应用版本可直接回退；image_urls_json 是向后兼容的扩展列，旧版本会忽略它。"
    "数据库降级保留该列和多图数据，重新升级时会幂等复用，避免因回滚丢失运营素材。"
)


def _columns(connection, backend: str, database: str) -> set[str]:
    if backend == "mysql":
        return {
            str(row["COLUMN_NAME"])
            for row in connection.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=? AND TABLE_NAME='community_posts'",
                (database,),
            ).fetchall()
        }
    return {str(row["name"]) for row in connection.execute("PRAGMA table_info(community_posts)").fetchall()}


def upgrade(connection, backend: str, database: str = "") -> None:
    """Persist community cover galleries without losing legacy primary covers."""
    columns = _columns(connection, backend, database)
    if not columns:
        return
    if "image_urls_json" not in columns:
        column_type = "LONGTEXT" if backend == "mysql" else "TEXT"
        connection.execute(f"ALTER TABLE community_posts ADD COLUMN image_urls_json {column_type}")

    rows = connection.execute(
        "SELECT post_id, image_url, image_urls_json FROM community_posts"
    ).fetchall()
    for raw in rows:
        row = dict(raw)
        primary_url = str(row.get("image_url") or "").strip()
        raw_gallery = row.get("image_urls_json")
        try:
            gallery = json.loads(raw_gallery) if isinstance(raw_gallery, str) else raw_gallery
        except json.JSONDecodeError:
            gallery = None
        if isinstance(gallery, list) and gallery:
            continue
        if not primary_url:
            continue
        connection.execute(
            "UPDATE community_posts SET image_urls_json=? WHERE post_id=?",
            (json.dumps([primary_url], ensure_ascii=False), row["post_id"]),
        )


def downgrade(connection, backend: str, database: str = "") -> None:
    """Apply the documented expand-only rollback and retain all gallery data."""
    return None
