from __future__ import annotations

import json
import sqlite3

from app.admin_service import AdminService
from app.migrations.versions import v20260807_23_community_post_image_gallery


def test_community_post_persists_ordered_cover_gallery_and_keeps_legacy_primary(tmp_path):
    service = AdminService(tmp_path / "community-cover-gallery.db")
    first = "https://cdn.example.com/community/first.webp"
    second = "https://cdn.example.com/community/second.webp"
    third = "https://cdn.example.com/community/third.webp"

    created = service.save_community_post(
        {
            "title": "三图灵感",
            "image_url": second,
            "image_urls": [first, second, third, first],
            "status": "published",
        }
    )

    assert created["image_url"] == second
    assert created["image_urls"] == [second, first, third]

    updated = service.save_community_post(
        {
            "title": "三图灵感（更新）",
            "image_urls": [third, first],
            "status": "published",
        },
        post_id=created["id"],
    )

    assert updated["image_url"] == third
    assert updated["image_urls"] == [third, first]
    assert service.get_community_post(created["id"])["image_urls"] == [third, first]


def test_community_cover_gallery_migration_backfills_legacy_primary(tmp_path):
    path = tmp_path / "legacy-community-cover.db"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE community_posts (post_id TEXT PRIMARY KEY, image_url TEXT)")
    connection.execute(
        "INSERT INTO community_posts (post_id, image_url) VALUES (?, ?)",
        ("inspo_legacy", "https://cdn.example.com/community/legacy.webp"),
    )

    v20260807_23_community_post_image_gallery.upgrade(connection, "sqlite")
    v20260807_23_community_post_image_gallery.upgrade(connection, "sqlite")

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(community_posts)").fetchall()}
    stored = connection.execute(
        "SELECT image_urls_json FROM community_posts WHERE post_id='inspo_legacy'"
    ).fetchone()
    connection.close()

    assert "image_urls_json" in columns
    assert json.loads(stored["image_urls_json"]) == ["https://cdn.example.com/community/legacy.webp"]


def test_community_cover_gallery_downgrade_preserves_expand_only_data(tmp_path):
    path = tmp_path / "community-cover-expand-only.db"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE community_posts (post_id TEXT PRIMARY KEY, image_url TEXT)")
    connection.execute(
        "INSERT INTO community_posts (post_id, image_url) VALUES (?, ?)",
        ("inspo_rollback", "https://cdn.example.com/community/rollback.webp"),
    )
    v20260807_23_community_post_image_gallery.upgrade(connection, "sqlite")

    v20260807_23_community_post_image_gallery.downgrade(connection, "sqlite")

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(community_posts)").fetchall()}
    gallery = connection.execute(
        "SELECT image_urls_json FROM community_posts WHERE post_id='inspo_rollback'"
    ).fetchone()["image_urls_json"]
    connection.close()
    assert "image_urls_json" in columns
    assert json.loads(gallery) == ["https://cdn.example.com/community/rollback.webp"]
