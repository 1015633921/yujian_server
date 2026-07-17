from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest


def mysql_test_configuration() -> dict[str, str]:
    database = os.getenv("COMMUNITY_MYSQL_TEST_DATABASE", "")
    host = os.getenv("COMMUNITY_MYSQL_TEST_HOST", "127.0.0.1")
    if os.getenv("RUN_COMMUNITY_MYSQL_INTEGRATION") != "1":
        pytest.skip("set RUN_COMMUNITY_MYSQL_INTEGRATION=1 to run isolated community MySQL tests")
    if "community_test" not in database.lower():
        pytest.fail("COMMUNITY_MYSQL_TEST_DATABASE must contain 'community_test'")
    if host not in {"127.0.0.1", "localhost", "mysql"}:
        pytest.fail("community MySQL tests only allow an isolated local/container host")
    return {
        "MYSQL_HOST": host,
        "MYSQL_PORT": os.getenv("COMMUNITY_MYSQL_TEST_PORT", "3306"),
        "MYSQL_DATABASE": database,
        "MYSQL_USER": os.environ["COMMUNITY_MYSQL_TEST_USER"],
        "MYSQL_PASSWORD": os.environ["COMMUNITY_MYSQL_TEST_PASSWORD"],
    }


@pytest.mark.mysql_integration
def test_mysql_migration_roundtrip_and_idempotent_social_writes(monkeypatch):
    config = mysql_test_configuration()
    monkeypatch.setenv("DATABASE_BACKEND", "mysql")
    monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "false")
    for key, value in config.items():
        monkeypatch.setenv(key, value)

    from app import database as database_module
    from app.admin_service import AdminService
    import app.community_ugc_service as community_service_module
    from app.community_ugc_service import (
        CommunityNotFound,
        CommunityUGCService,
        CommunityValidation,
    )
    from app.migrations.runner import downgrade, upgrade
    from app.migrations.versions.v20260717_09_community_ugc_core import VERSION
    from app.order_service import OrderService
    from app.repository import AssessmentRepository

    database_module._schema_ready.discard(config["MYSQL_DATABASE"])
    AdminService()
    order_service = OrderService()
    repository = AssessmentRepository()
    upgrade("mysql")
    assert downgrade("mysql", steps=1) == [VERSION]
    assert upgrade("mysql") == [VERSION]

    timestamp = "2026-07-17T00:00:00+00:00"
    monkeypatch.setattr(community_service_module, "now_iso", lambda: timestamp)
    service = CommunityUGCService()
    with service.connect() as connection:
        connection.execute("DELETE FROM community_ugc_reports WHERE reporter_user_id LIKE 'community-mysql-%'")
        connection.execute("DELETE FROM community_ugc_follows WHERE follower_user_id LIKE 'community-mysql-%'")
        connection.execute("DELETE FROM community_ugc_comments WHERE author_user_id LIKE 'community-mysql-%'")
        connection.execute("DELETE FROM community_ugc_saves WHERE user_id LIKE 'community-mysql-%'")
        connection.execute("DELETE FROM community_ugc_likes WHERE user_id LIKE 'community-mysql-%'")
        connection.execute("DELETE FROM community_ugc_posts WHERE owner_user_id LIKE 'community-mysql-%'")
        connection.execute(
            "DELETE FROM users WHERE user_id IN "
            "('community-mysql-a-new', 'community-mysql-b-new')"
        )
    for user_id in ("community-mysql-a", "community-mysql-b"):
        repository.upsert_user(
            {"user_id": user_id, "nickname": user_id, "source": "test", "updated_at": timestamp}
        )

    post = service.create_post(
        "community-mysql-a", {"title": "MySQL", "content": "双后端测试", "image_urls": [], "tags": []}
    )
    post = service.submit_post(post["post_id"], "community-mysql-a")
    assert post["status"] == "published"
    assert service.set_like(post["post_id"], "community-mysql-b", True)["changed"] is True
    assert service.set_like(post["post_id"], "community-mysql-b", True)["changed"] is False
    assert service.set_save(post["post_id"], "community-mysql-b", True)["changed"] is True
    comment = service.create_comment(post["post_id"], "community-mysql-b", "MySQL 评论")
    assert service.set_follow("community-mysql-a", "community-mysql-b", True)["changed"] is True
    assert service.create_report(
        "community-mysql-b",
        {"target_type": "post", "target_id": post["post_id"], "reason": "测试", "detail": None},
    )["duplicate"] is False
    with service.connect() as connection:
        connection.execute(
            "INSERT INTO community_ugc_likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
            (post["post_id"], "community-mysql-b-new", timestamp),
        )
        connection.execute(
            "INSERT INTO community_ugc_saves (post_id, user_id, created_at) VALUES (?, ?, ?)",
            (post["post_id"], "community-mysql-b-new", timestamp),
        )
        connection.execute(
            "INSERT INTO community_ugc_follows "
            "(follower_user_id, followed_user_id, created_at) VALUES (?, ?, ?)",
            ("community-mysql-b-new", "community-mysql-a", timestamp),
        )
        connection.execute(
            "INSERT INTO community_ugc_reports "
            "(report_id, reporter_user_id, target_type, target_id, reason, detail, status, "
            "created_at, updated_at) VALUES (?, ?, 'post', ?, '碰撞', NULL, 'open', ?, ?)",
            ("community-mysql-collision-report", "community-mysql-b-new", post["post_id"], timestamp, timestamp),
        )

    draft = service.create_post(
        "community-mysql-a",
        {"title": "同值更新", "content": "rowcount 回归", "image_urls": [], "tags": []},
    )
    assert service.update_post(draft["post_id"], "community-mysql-a", {"title": "同值更新"})[
        "title"
    ] == "同值更新"

    repository.reassign_user_id(
        "community-mysql-b", "community-mysql-b-new", "2026-07-17T01:00:00+00:00"
    )
    repository.reassign_user_id(
        "community-mysql-a", "community-mysql-a-new", "2026-07-17T01:00:00+00:00"
    )
    with service.connect() as connection:
        assert connection.execute(
            "SELECT owner_user_id FROM community_ugc_posts WHERE post_id = ?", (post["post_id"],)
        ).fetchone()["owner_user_id"] == "community-mysql-a-new"
        assert connection.execute(
            "SELECT author_user_id FROM community_ugc_comments WHERE comment_id = ?",
            (comment["comment_id"],),
        ).fetchone()["author_user_id"] == "community-mysql-b-new"
        for table, column in (
            ("community_ugc_likes", "user_id"),
            ("community_ugc_saves", "user_id"),
            ("community_ugc_reports", "reporter_user_id"),
        ):
            assert connection.execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE {column} = 'community-mysql-b'"
            ).fetchone()["total"] == 0
        assert connection.execute(
            "SELECT COUNT(*) AS total FROM community_ugc_follows "
            "WHERE follower_user_id IN ('community-mysql-a', 'community-mysql-b') "
            "OR followed_user_id IN ('community-mysql-a', 'community-mysql-b')"
        ).fetchone()["total"] == 0
        for table in ("community_ugc_likes", "community_ugc_saves"):
            assert connection.execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE post_id = ? AND user_id = ?",
                (post["post_id"], "community-mysql-b-new"),
            ).fetchone()["total"] == 1
        assert connection.execute(
            "SELECT COUNT(*) AS total FROM community_ugc_reports "
            "WHERE target_type = 'post' AND target_id = ? AND reporter_user_id = ?",
            (post["post_id"], "community-mysql-b-new"),
        ).fetchone()["total"] == 1

    for user_id in ("community-mysql-c", "community-mysql-d"):
        repository.upsert_user(
            {"user_id": user_id, "nickname": user_id, "source": "test", "updated_at": timestamp}
        )
    source = service.create_post(
        "community-mysql-c",
        {"title": "并发来源", "content": "来源撤回", "image_urls": [], "tags": []},
    )
    source = service.submit_post(source["post_id"], "community-mysql-c")
    derived = service.create_post(
        "community-mysql-d",
        {
            "title": "并发派生",
            "content": "提交必须重检",
            "image_urls": [],
            "tags": [],
            "source_post_id": source["post_id"],
        },
    )
    blocker = service.connect()
    try:
        blocker.execute(
            "SELECT post_id FROM community_ugc_posts WHERE post_id = ? FOR UPDATE",
            (source["post_id"],),
        ).fetchone()
        blocker.execute(
            "UPDATE community_ugc_posts SET status = 'draft', published_at = NULL WHERE post_id = ?",
            (source["post_id"],),
        )
        barrier = threading.Barrier(2)

        def submit_derived():
            barrier.wait(timeout=5)
            return service.submit_post(derived["post_id"], "community-mysql-d")

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(submit_derived)
            barrier.wait(timeout=5)
            blocker.raw.commit()
            with pytest.raises(CommunityValidation, match="source_post_id"):
                future.result(timeout=10)
    finally:
        blocker.raw.close()

    stale_user_id = "community-mysql-e"
    migrated_user_id = "community-mysql-e-new"
    with service.connect() as connection:
        connection.execute(
            "DELETE FROM community_favorites WHERE user_id IN (?, ?)",
            (stale_user_id, migrated_user_id),
        )
        connection.execute(
            "DELETE FROM users WHERE user_id IN (?, ?)",
            (stale_user_id, migrated_user_id),
        )
    repository.upsert_user(
        {
            "user_id": stale_user_id,
            "nickname": stale_user_id,
            "source": "test",
            "updated_at": timestamp,
        }
    )
    reassign_has_user_lock = threading.Event()
    allow_reassign = threading.Event()
    favorite_started = threading.Event()
    original_merge_favorites = repository._merge_community_favorites
    original_lock_users = order_service._lock_existing_users

    def gated_merge_favorites(connection, old_user_id, new_user_id):
        reassign_has_user_lock.set()
        assert allow_reassign.wait(timeout=5)
        return original_merge_favorites(connection, old_user_id, new_user_id)

    def observed_favorite_user_lock(connection, *user_ids):
        favorite_started.set()
        return original_lock_users(connection, *user_ids)

    monkeypatch.setattr(repository, "_merge_community_favorites", gated_merge_favorites)
    monkeypatch.setattr(order_service, "_lock_existing_users", observed_favorite_user_lock)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            reassign_future = executor.submit(
                repository.reassign_user_id,
                stale_user_id,
                migrated_user_id,
                "2026-07-17T02:00:00+00:00",
            )
            assert reassign_has_user_lock.wait(timeout=5)
            favorite_future = executor.submit(
                order_service.save_community_favorite,
                {"user_id": stale_user_id, "post_id": "community-mysql-editorial"},
            )
            assert favorite_started.wait(timeout=5)
            allow_reassign.set()
            assert reassign_future.result(timeout=10)["user_id"] == migrated_user_id
            with pytest.raises(ValueError, match="用户不存在"):
                favorite_future.result(timeout=10)
    finally:
        allow_reassign.set()

    with service.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) AS total FROM community_favorites WHERE user_id = ?",
            (stale_user_id,),
        ).fetchone()["total"] == 0

    interaction_post = service.create_post(
        "community-mysql-c",
        {"title": "互动竞态", "content": "撤回优先", "image_urls": [], "tags": []},
    )
    interaction_post = service.submit_post(interaction_post["post_id"], "community-mysql-c")
    blocker = service.connect()
    try:
        blocker.execute(
            "SELECT post_id FROM community_ugc_posts WHERE post_id = ? FOR UPDATE",
            (interaction_post["post_id"],),
        ).fetchone()
        blocker.execute(
            "UPDATE community_ugc_posts SET status = 'draft', published_at = NULL WHERE post_id = ?",
            (interaction_post["post_id"],),
        )
        barrier = threading.Barrier(2)

        def like_withdrawn():
            barrier.wait(timeout=5)
            return service.set_like(interaction_post["post_id"], "community-mysql-d", True)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(like_withdrawn)
            barrier.wait(timeout=5)
            blocker.raw.commit()
            with pytest.raises(CommunityNotFound, match="帖子不存在"):
                future.result(timeout=10)
    finally:
        blocker.raw.close()
