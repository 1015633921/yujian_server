from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app import community_ugc_api as api_module
from app.admin_service import AdminService
from app.community_ugc_service import (
    CommunityNotFound,
    CommunityUGCService,
    CommunityValidation,
)
from app.main import app
from app.migrations.runner import upgrade
from app.order_service import OrderService
from app.repository import AssessmentRepository
from app.user_sessions import UserPrincipal, UserSessionService, require_current_user
from app import user_sessions as user_sessions_module


@dataclass
class CommunityHarness:
    client: TestClient
    service: CommunityUGCService
    current_user: dict[str, str]
    order_service: OrderService

    def as_user(self, user_id: str) -> None:
        self.current_user["user_id"] = user_id

    def create(self, **overrides):
        payload = {"title": "清透日常", "content": "记录一条真实的手串设计灵感。"}
        payload.update(overrides)
        return self.client.post("/api/v1/community/posts", json=payload)

    def publish_without_moderation(self, monkeypatch, **overrides) -> dict:
        monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "false")
        created = self.create(**overrides)
        assert created.status_code == 201, created.text
        post_id = created.json()["data"]["post_id"]
        submitted = self.client.post(f"/api/v1/community/posts/{post_id}/submit")
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["data"]["status"] == "published"
        return submitted.json()["data"]


@pytest.fixture
def community(tmp_path, monkeypatch):
    db_path = tmp_path / "community.db"
    repository = AssessmentRepository(db_path)
    order_service = OrderService(db_path)
    AdminService(db_path)
    upgrade("sqlite", db_path)
    timestamp = "2026-07-17T00:00:00+00:00"
    for user_id, nickname in (("user-a", "阿澄"), ("user-b", "山岚")):
        repository.upsert_user(
            {
                "user_id": user_id,
                "nickname": nickname,
                "source": "test",
                "updated_at": timestamp,
            }
        )

    service = CommunityUGCService(db_path)
    monkeypatch.setattr(api_module, "community_ugc_service", service)
    monkeypatch.setenv("COMMUNITY_UGC_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_UGC_WRITES_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "true")

    current_user = {"user_id": "user-a"}

    def current_principal():
        return UserPrincipal(current_user["user_id"], f"session-{current_user['user_id']}")

    app.dependency_overrides[require_current_user] = current_principal
    with TestClient(app) as client:
        yield CommunityHarness(client, service, current_user, order_service)
    app.dependency_overrides.pop(require_current_user, None)


def test_flags_default_closed_and_readiness_is_non_mutating(community, monkeypatch):
    monkeypatch.delenv("COMMUNITY_UGC_ENABLED", raising=False)
    monkeypatch.delenv("COMMUNITY_UGC_WRITES_ENABLED", raising=False)

    readiness = community.client.get("/api/v1/community/readiness")
    feed = community.client.get("/api/v1/community/posts")
    write = community.create()

    assert readiness.status_code == 200
    assert readiness.json()["data"] == {
        "schema_ready": True,
        "migration_version": "20260717_09_community_ugc_core",
        "migration_applied": True,
        "missing_tables": [],
        "read_enabled": False,
        "write_enabled": False,
        "moderation_required": True,
        "read_available": False,
        "write_available": False,
    }
    assert feed.status_code == 503
    assert write.status_code == 503


def test_enabled_feature_fails_closed_without_migration_and_readiness_does_not_create_db(
    tmp_path, monkeypatch
):
    missing_path = tmp_path / "missing-community.db"
    missing_service = CommunityUGCService(missing_path)
    monkeypatch.setattr(api_module, "community_ugc_service", missing_service)
    monkeypatch.setenv("COMMUNITY_UGC_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_UGC_WRITES_ENABLED", "true")

    with TestClient(app) as client:
        readiness = client.get("/api/v1/community/readiness")
        feed = client.get("/api/v1/community/posts")

    assert readiness.status_code == 200
    assert readiness.json()["data"]["reason"] == "database_missing"
    assert feed.status_code == 503
    assert missing_path.exists() is False


def test_owner_crud_visibility_and_conservative_status_matrix(community, monkeypatch):
    created = community.create(tags=["日常", "清透"])
    assert created.status_code == 201
    post = created.json()["data"]
    post_id = post["post_id"]
    assert post["status"] == "draft"
    assert community.client.get(f"/api/v1/community/posts/{post_id}").status_code == 404

    community.as_user("user-b")
    assert community.client.get(f"/api/v1/community/me/posts/{post_id}").status_code == 404
    assert community.client.patch(
        f"/api/v1/community/posts/{post_id}", json={"title": "越权修改"}
    ).status_code == 404
    assert community.client.delete(f"/api/v1/community/posts/{post_id}").status_code == 404

    community.as_user("user-a")
    edited = community.client.patch(
        f"/api/v1/community/posts/{post_id}", json={"title": "清透日常 · 修改"}
    )
    assert edited.status_code == 200
    assert edited.json()["data"]["title"].endswith("修改")

    submitted = community.client.post(f"/api/v1/community/posts/{post_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["data"]["status"] == "pending"
    assert submitted.json()["data"]["changed"] is True
    submitted_again = community.client.post(f"/api/v1/community/posts/{post_id}/submit")
    assert submitted_again.json()["data"]["changed"] is False
    assert community.client.patch(
        f"/api/v1/community/posts/{post_id}", json={"title": "待审时不可改"}
    ).status_code == 409
    assert community.client.get(f"/api/v1/community/posts/{post_id}").status_code == 404

    published = community.service.publish_for_moderation(post_id)
    assert published["status"] == "published"
    assert community.client.get(f"/api/v1/community/posts/{post_id}").status_code == 200
    assert [item["post_id"] for item in community.client.get("/api/v1/community/posts").json()["data"]] == [post_id]

    withdrawn = community.client.post(f"/api/v1/community/posts/{post_id}/withdraw")
    assert withdrawn.status_code == 200
    assert withdrawn.json()["data"]["status"] == "draft"
    assert withdrawn.json()["data"]["changed"] is True
    assert community.client.post(f"/api/v1/community/posts/{post_id}/withdraw").json()["data"]["changed"] is False
    assert community.client.get(f"/api/v1/community/posts/{post_id}").status_code == 404

    monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "false")
    directly_published = community.client.post(f"/api/v1/community/posts/{post_id}/submit")
    assert directly_published.json()["data"]["status"] == "published"
    directly_published_again = community.client.post(
        f"/api/v1/community/posts/{post_id}/submit"
    )
    assert directly_published_again.status_code == 200
    assert directly_published_again.json()["data"]["changed"] is False
    assert community.client.get(f"/api/v1/community/posts/{post_id}").status_code == 200

    deleted = community.client.delete(f"/api/v1/community/posts/{post_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True
    assert community.client.get(f"/api/v1/community/posts/{post_id}").status_code == 404


def test_invalid_moderation_flag_fails_closed_to_pending(community, monkeypatch):
    monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "invalid")
    created = community.create(title="错误开关仍需审核")
    post_id = created.json()["data"]["post_id"]

    submitted = community.client.post(f"/api/v1/community/posts/{post_id}/submit")

    assert submitted.status_code == 200
    assert submitted.json()["data"]["status"] == "pending"


def test_writes_derive_owner_from_principal_and_reject_untrusted_media(community):
    spoofed = community.client.post(
        "/api/v1/community/posts",
        json={"user_id": "user-b", "title": "伪造", "content": "客户端不能指定 owner"},
    )
    media = community.create(image_urls=["https://attacker.example/image.png"])
    foreign_design = community.order_service.save_design(
        {"user_id": "user-b", "design": {}, "sequence": []}
    )
    design = community.create(design_id=foreign_design["design_id"])

    assert spoofed.status_code == 422
    assert media.status_code == 422
    assert design.status_code == 400
    assert community.service.list_owned_posts("user-b") == []


def test_owned_design_and_public_source_references_are_verified(community, monkeypatch):
    own_design = community.order_service.save_design(
        {"user_id": "user-a", "design": {"name": "自有设计"}, "sequence": []}
    )
    source = community.publish_without_moderation(
        monkeypatch, title="来源灵感", design_id=own_design["design_id"]
    )
    assert source["design_id"] == own_design["design_id"]

    community.as_user("user-b")
    derived = community.create(title="引用公开灵感", source_post_id=source["post_id"])
    assert derived.status_code == 201
    assert derived.json()["data"]["source_post_id"] == source["post_id"]

    community.as_user("user-a")
    assert community.client.post(
        f"/api/v1/community/posts/{source['post_id']}/withdraw"
    ).status_code == 200
    community.as_user("user-b")
    invalid_submit = community.client.post(
        f"/api/v1/community/posts/{derived.json()['data']['post_id']}/submit"
    )
    assert invalid_submit.status_code == 400
    assert community.service.get_owned_post(
        derived.json()["data"]["post_id"], "user-b"
    )["status"] == "draft"
    hidden_source = community.create(title="不能引用已撤回来源", source_post_id=source["post_id"])
    assert hidden_source.status_code == 400


def test_explicit_null_clears_optional_references_but_not_required_fields(
    community, monkeypatch
):
    design = community.order_service.save_design(
        {"user_id": "user-a", "design": {"name": "待清除关联"}, "sequence": []}
    )
    source = community.publish_without_moderation(monkeypatch, title="可清除来源")
    draft = community.create(
        title="含可选关联",
        design_id=design["design_id"],
        source_post_id=source["post_id"],
    ).json()["data"]

    cleared = community.client.patch(
        f"/api/v1/community/posts/{draft['post_id']}",
        json={"design_id": None, "source_post_id": None},
    )

    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["design_id"] is None
    assert cleared.json()["data"]["source_post_id"] is None
    assert community.client.patch(
        f"/api/v1/community/posts/{draft['post_id']}", json={"title": None}
    ).status_code == 422
    assert community.client.patch(
        f"/api/v1/community/posts/{draft['post_id']}", json={"tags": None}
    ).status_code == 422


def test_pending_source_is_revalidated_before_trusted_publish(community, monkeypatch):
    source = community.publish_without_moderation(monkeypatch, title="审核来源")
    community.as_user("user-b")
    derived = community.create(title="待审核引用", source_post_id=source["post_id"]).json()["data"]
    monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "true")
    submitted = community.client.post(f"/api/v1/community/posts/{derived['post_id']}/submit")
    assert submitted.json()["data"]["status"] == "pending"

    community.as_user("user-a")
    assert community.client.post(
        f"/api/v1/community/posts/{source['post_id']}/withdraw"
    ).status_code == 200

    with pytest.raises(CommunityValidation, match="source_post_id"):
        community.service.publish_for_moderation(derived["post_id"])


def test_design_is_revalidated_on_submit_and_moderation_publish(community, monkeypatch):
    first_design = community.order_service.save_design(
        {"user_id": "user-a", "design": {"name": "提交重检"}, "sequence": []}
    )
    draft = community.create(title="设计提交重检", design_id=first_design["design_id"]).json()[
        "data"
    ]
    with pytest.raises(ValueError, match="灵感帖子引用"):
        community.order_service.delete_design(first_design["design_id"], "user-a")
    with community.order_service.connect() as connection:
        connection.execute(
            "DELETE FROM diy_designs WHERE design_id = ?", (first_design["design_id"],)
        )
    assert community.client.post(
        f"/api/v1/community/posts/{draft['post_id']}/submit"
    ).status_code == 400

    second_design = community.order_service.save_design(
        {"user_id": "user-a", "design": {"name": "审核重检"}, "sequence": []}
    )
    pending = community.create(
        title="设计审核重检", design_id=second_design["design_id"]
    ).json()["data"]
    monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "true")
    assert community.client.post(
        f"/api/v1/community/posts/{pending['post_id']}/submit"
    ).json()["data"]["status"] == "pending"
    with community.order_service.connect() as connection:
        connection.execute(
            "DELETE FROM diy_designs WHERE design_id = ?", (second_design["design_id"],)
        )
    with pytest.raises(CommunityValidation, match="design_id"):
        community.service.publish_for_moderation(pending["post_id"])


def test_idempotent_like_save_comment_follow_and_report_flows(community, monkeypatch):
    post = community.publish_without_moderation(monkeypatch)
    post_id = post["post_id"]
    community.as_user("user-b")

    first_like = community.client.put(f"/api/v1/community/posts/{post_id}/like").json()["data"]
    second_like = community.client.put(f"/api/v1/community/posts/{post_id}/like").json()["data"]
    assert (first_like["changed"], second_like["changed"], second_like["like_count"]) == (True, False, 1)
    first_unlike = community.client.delete(f"/api/v1/community/posts/{post_id}/like").json()["data"]
    second_unlike = community.client.delete(f"/api/v1/community/posts/{post_id}/like").json()["data"]
    assert (first_unlike["changed"], second_unlike["changed"], second_unlike["like_count"]) == (True, False, 0)

    first_save = community.client.put(f"/api/v1/community/posts/{post_id}/save").json()["data"]
    second_save = community.client.put(f"/api/v1/community/posts/{post_id}/save").json()["data"]
    assert (first_save["changed"], second_save["changed"], second_save["save_count"]) == (True, False, 1)
    saved = community.client.get("/api/v1/community/me/saved-posts").json()["data"]
    assert [item["post_id"] for item in saved] == [post_id]
    assert community.client.delete(f"/api/v1/community/posts/{post_id}/save").json()["data"]["changed"] is True
    assert community.client.delete(f"/api/v1/community/posts/{post_id}/save").json()["data"]["changed"] is False

    comment = community.client.post(
        f"/api/v1/community/posts/{post_id}/comments", json={"content": "喜欢这组清透配色"}
    )
    assert comment.status_code == 201
    comment_id = comment.json()["data"]["comment_id"]
    assert len(community.client.get(f"/api/v1/community/posts/{post_id}/comments").json()["data"]) == 1

    community.as_user("user-a")
    assert community.client.delete(f"/api/v1/community/comments/{comment_id}").status_code == 404
    community.as_user("user-b")
    assert community.client.delete(f"/api/v1/community/comments/{comment_id}").json()["data"]["changed"] is True
    assert community.client.delete(f"/api/v1/community/comments/{comment_id}").json()["data"]["changed"] is False
    assert community.client.get(f"/api/v1/community/posts/{post_id}/comments").json()["data"] == []

    followed = community.client.put("/api/v1/community/users/user-a/follow").json()["data"]
    followed_again = community.client.put("/api/v1/community/users/user-a/follow").json()["data"]
    assert (followed["changed"], followed_again["changed"], followed_again["follower_count"]) == (True, False, 1)
    assert community.client.get("/api/v1/community/me/following").json()["data"][0]["user_id"] == "user-a"
    assert community.client.put("/api/v1/community/users/user-b/follow").status_code == 400
    assert community.client.delete("/api/v1/community/users/user-a/follow").json()["data"]["changed"] is True
    assert community.client.delete("/api/v1/community/users/user-a/follow").json()["data"]["changed"] is False

    first_report = community.client.post(
        "/api/v1/community/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "其他", "detail": "测试举报"},
    )
    second_report = community.client.post(
        "/api/v1/community/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "重复请求"},
    )
    assert first_report.status_code == 201
    assert second_report.status_code == 201
    assert first_report.json()["data"]["report_id"] == second_report.json()["data"]["report_id"]
    assert first_report.json()["data"]["duplicate"] is False
    assert second_report.json()["data"]["duplicate"] is True


def test_withdrawn_post_hides_comments_and_rejects_new_interactions(community, monkeypatch):
    post = community.publish_without_moderation(monkeypatch, title="即将撤回")
    post_id = post["post_id"]
    community.as_user("user-b")
    comment = community.client.post(
        f"/api/v1/community/posts/{post_id}/comments", json={"content": "撤回前评论"}
    )
    assert comment.status_code == 201

    community.as_user("user-a")
    assert community.client.post(f"/api/v1/community/posts/{post_id}/withdraw").status_code == 200
    community.as_user("user-b")

    assert community.client.get(f"/api/v1/community/posts/{post_id}/comments").status_code == 404
    assert community.client.put(f"/api/v1/community/posts/{post_id}/like").status_code == 404
    assert community.client.put(f"/api/v1/community/posts/{post_id}/save").status_code == 404
    assert community.client.post(
        f"/api/v1/community/posts/{post_id}/comments", json={"content": "不能新增"}
    ).status_code == 404
    assert community.client.post(
        "/api/v1/community/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "不可见"},
    ).status_code == 404


def test_readiness_hot_path_uses_short_lived_cache_and_can_be_invalidated(
    community, monkeypatch
):
    calls = {"count": 0}
    uncached = community.service._readiness_uncached

    def counted_readiness():
        calls["count"] += 1
        return uncached()

    monkeypatch.setattr(community.service, "_readiness_uncached", counted_readiness)
    monkeypatch.setenv("COMMUNITY_READINESS_CACHE_TTL_SECONDS", "60")
    community.service.clear_readiness_cache()

    assert community.client.get("/api/v1/community/posts").status_code == 200
    assert community.client.get("/api/v1/community/posts").status_code == 200
    assert calls["count"] == 1

    community.service.clear_readiness_cache()
    assert community.client.get("/api/v1/community/posts").status_code == 200
    assert calls["count"] == 2
    assert community.client.get("/api/v1/community/readiness").status_code == 200
    assert calls["count"] == 2
    community.service.clear_readiness_cache()
    assert community.client.get("/api/v1/community/readiness").status_code == 200
    assert calls["count"] == 3


def test_concurrent_readiness_cache_miss_uses_one_database_probe(community, monkeypatch):
    calls = {"count": 0}
    original = community.service._readiness_uncached
    start = threading.Barrier(3)
    entered = threading.Event()
    release = threading.Event()

    def slow_readiness():
        calls["count"] += 1
        entered.set()
        assert release.wait(timeout=5)
        return original()

    def read():
        start.wait(timeout=5)
        return community.service.readiness()

    monkeypatch.setattr(community.service, "_readiness_uncached", slow_readiness)
    community.service.clear_readiness_cache()
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(read)
        second = executor.submit(read)
        start.wait(timeout=5)
        assert entered.wait(timeout=5)
        release.set()
        results = (first.result(timeout=5), second.result(timeout=5))

    assert calls["count"] == 1
    assert all(result["schema_ready"] is True for result in results)


def test_write_endpoint_requires_bearer_when_not_overridden(community):
    app.dependency_overrides.pop(require_current_user, None)
    response = community.client.post(
        "/api/v1/community/posts", json={"title": "未登录", "content": "不应写入"}
    )
    assert response.status_code == 401


def test_real_bearer_sessions_enforce_a_b_ownership_and_reject_forgery(community, monkeypatch):
    app.dependency_overrides.pop(require_current_user, None)
    isolated_sessions = UserSessionService(community.service.db_path)
    monkeypatch.setattr(user_sessions_module, "session_service", isolated_sessions)
    session_a = isolated_sessions.create("user-a")
    session_b = isolated_sessions.create("user-b")
    headers_a = {"Authorization": f"Bearer {session_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {session_b['access_token']}"}

    created = community.client.post(
        "/api/v1/community/posts",
        headers=headers_a,
        json={"title": "Bearer 所有权", "content": "真实会话集成验证"},
    )
    assert created.status_code == 201
    post_id = created.json()["data"]["post_id"]

    assert community.client.get(
        f"/api/v1/community/me/posts/{post_id}", headers=headers_b
    ).status_code == 404
    assert community.client.patch(
        f"/api/v1/community/posts/{post_id}", headers=headers_b, json={"title": "B 越权"}
    ).status_code == 404
    assert community.client.delete(
        f"/api/v1/community/posts/{post_id}", headers=headers_b
    ).status_code == 404
    assert community.client.get(
        f"/api/v1/community/me/posts/{post_id}", headers=headers_a
    ).status_code == 200
    assert community.client.post(
        "/api/v1/community/posts",
        headers={"Authorization": "Bearer " + "x" * 64},
        json={"title": "伪造", "content": "不应通过"},
    ).status_code == 401


def _migrated_repository(db_path):
    repository = AssessmentRepository(db_path)
    OrderService(db_path)
    AdminService(db_path)
    upgrade("sqlite", db_path)
    return repository


def _upsert_test_user(repository, user_id: str) -> None:
    repository.upsert_user(
        {
            "user_id": user_id,
            "nickname": user_id,
            "source": "test",
            "updated_at": "2026-07-17T00:00:00+00:00",
        }
    )


def _insert_test_post(connection, post_id: str, owner_user_id: str) -> None:
    connection.execute(
        "INSERT INTO community_ugc_posts "
        "(post_id, owner_user_id, title, content, image_urls_json, tags_json, design_id, "
        "source_post_id, status, submitted_at, published_at, deleted_at, created_at, updated_at) "
        "VALUES (?, ?, '测试帖子', '迁移测试', '[]', '[]', NULL, NULL, 'published', ?, ?, NULL, ?, ?)",
        (
            post_id,
            owner_user_id,
            "2026-07-17T00:00:00+00:00",
            "2026-07-17T00:00:00+00:00",
            "2026-07-17T00:00:00+00:00",
            "2026-07-17T00:00:00+00:00",
        ),
    )


def test_reassign_user_id_merges_all_community_rows_and_unique_collisions(tmp_path):
    repository = _migrated_repository(tmp_path / "community-user-id.db")
    old_user_id = "legacy-community-user"
    new_user_id = "100000000001"
    other_user_id = "community-other"
    _upsert_test_user(repository, old_user_id)
    _upsert_test_user(repository, other_user_id)
    early = "2026-07-17T00:00:00+00:00"
    late = "2026-07-17T01:00:00+00:00"

    with repository.connect() as connection:
        _insert_test_post(connection, "post-owned", old_user_id)
        _insert_test_post(connection, "post-target", other_user_id)
        for table in ("community_ugc_likes", "community_ugc_saves"):
            connection.execute(
                f"INSERT INTO {table} (post_id, user_id, created_at) VALUES (?, ?, ?)",
                ("post-target", old_user_id, early),
            )
            connection.execute(
                f"INSERT INTO {table} (post_id, user_id, created_at) VALUES (?, ?, ?)",
                ("post-target", new_user_id, late),
            )
            connection.execute(
                f"INSERT INTO {table} (post_id, user_id, created_at) VALUES (?, ?, ?)",
                ("post-owned", old_user_id, late),
            )
        connection.execute(
            "INSERT INTO community_ugc_comments "
            "(comment_id, post_id, author_user_id, content, status, deleted_at, created_at, updated_at) "
            "VALUES ('comment-old', 'post-target', ?, '测试', 'active', NULL, ?, ?)",
            (old_user_id, early, early),
        )
        for follower, followed, created_at in (
            (old_user_id, other_user_id, early),
            (new_user_id, other_user_id, late),
            (other_user_id, old_user_id, early),
            (other_user_id, new_user_id, late),
            (old_user_id, new_user_id, early),
            (new_user_id, old_user_id, late),
        ):
            connection.execute(
                "INSERT INTO community_ugc_follows "
                "(follower_user_id, followed_user_id, created_at) VALUES (?, ?, ?)",
                (follower, followed, created_at),
            )
        for values in (
            ("report-old", old_user_id, "post", "post-target", "旧举报", "保留旧记录", early, early),
            ("report-new", new_user_id, "post", "post-target", "新举报", None, late, late),
            ("report-unique", old_user_id, "comment", "comment-old", "评论举报", None, late, late),
        ):
            connection.execute(
                "INSERT INTO community_ugc_reports "
                "(report_id, reporter_user_id, target_type, target_id, reason, detail, status, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)",
                values,
            )
        connection.execute(
            "INSERT INTO community_favorites "
            "(user_id, post_id, item_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (old_user_id, "editorial-shared", '{"snapshot":"old"}', early, early),
        )
        connection.execute(
            "INSERT INTO community_favorites "
            "(user_id, post_id, item_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (new_user_id, "editorial-shared", '{"snapshot":"new"}', late, late),
        )
        connection.execute(
            "INSERT INTO community_favorites "
            "(user_id, post_id, item_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (old_user_id, "editorial-unique", '{"snapshot":"unique"}', late, late),
        )

    migrated = repository.reassign_user_id(old_user_id, new_user_id, late)

    assert migrated["user_id"] == new_user_id
    assert repository.get_user(old_user_id) is None
    with repository.connect() as connection:
        assert connection.execute(
            "SELECT owner_user_id FROM community_ugc_posts WHERE post_id = 'post-owned'"
        ).fetchone()["owner_user_id"] == new_user_id
        assert connection.execute(
            "SELECT author_user_id FROM community_ugc_comments WHERE comment_id = 'comment-old'"
        ).fetchone()["author_user_id"] == new_user_id
        for table in ("community_ugc_likes", "community_ugc_saves"):
            collision = connection.execute(
                f"SELECT user_id, created_at FROM {table} WHERE post_id = 'post-target'"
            ).fetchall()
            assert [dict(row) for row in collision] == [
                {"user_id": new_user_id, "created_at": early}
            ]
            assert connection.execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE user_id = ?",
                (old_user_id,),
            ).fetchone()["total"] == 0
        follows = connection.execute(
            "SELECT follower_user_id, followed_user_id, created_at "
            "FROM community_ugc_follows ORDER BY follower_user_id, followed_user_id"
        ).fetchall()
        assert [dict(row) for row in follows] == [
            {
                "follower_user_id": new_user_id,
                "followed_user_id": other_user_id,
                "created_at": early,
            },
            {
                "follower_user_id": other_user_id,
                "followed_user_id": new_user_id,
                "created_at": early,
            },
        ]
        reports = connection.execute(
            "SELECT report_id, reporter_user_id, target_type, target_id, reason, detail "
            "FROM community_ugc_reports ORDER BY report_id"
        ).fetchall()
        assert [dict(row) for row in reports] == [
            {
                "report_id": "report-old",
                "reporter_user_id": new_user_id,
                "target_type": "post",
                "target_id": "post-target",
                "reason": "旧举报",
                "detail": "保留旧记录",
            },
            {
                "report_id": "report-unique",
                "reporter_user_id": new_user_id,
                "target_type": "comment",
                "target_id": "comment-old",
                "reason": "评论举报",
                "detail": None,
            },
        ]
        assert connection.execute(
            "SELECT COUNT(*) AS total FROM community_ugc_follows "
            "WHERE follower_user_id = followed_user_id OR follower_user_id = ? OR followed_user_id = ?",
            (old_user_id, old_user_id),
        ).fetchone()["total"] == 0
        assert connection.execute(
            "SELECT COUNT(*) AS total FROM community_ugc_reports WHERE reporter_user_id = ?",
            (old_user_id,),
        ).fetchone()["total"] == 0
        favorites = connection.execute(
            "SELECT user_id, post_id, item_json, created_at, updated_at "
            "FROM community_favorites ORDER BY post_id"
        ).fetchall()
        assert [
            {
                **dict(row),
                "item_json": json.loads(row["item_json"]),
            }
            for row in favorites
        ] == [
            {
                "user_id": new_user_id,
                "post_id": "editorial-shared",
                "item_json": {"snapshot": "new"},
                "created_at": early,
                "updated_at": late,
            },
            {
                "user_id": new_user_id,
                "post_id": "editorial-unique",
                "item_json": {"snapshot": "unique"},
                "created_at": late,
                "updated_at": late,
            },
        ]


def test_reassign_user_id_rolls_back_community_rows_with_user_update(tmp_path):
    repository = _migrated_repository(tmp_path / "community-user-id-rollback.db")
    old_user_id = "legacy-community-user"
    new_user_id = "100000000002"
    other_user_id = "community-other"
    timestamp = "2026-07-17T00:00:00+00:00"
    _upsert_test_user(repository, old_user_id)
    _upsert_test_user(repository, other_user_id)
    with repository.connect() as connection:
        _insert_test_post(connection, "post-rollback", old_user_id)
        connection.execute(
            "INSERT INTO community_ugc_likes VALUES ('post-rollback', ?, ?)",
            (old_user_id, timestamp),
        )
        connection.execute(
            "INSERT INTO community_ugc_saves VALUES ('post-rollback', ?, ?)",
            (old_user_id, timestamp),
        )
        connection.execute(
            "INSERT INTO community_ugc_comments VALUES "
            "('comment-rollback', 'post-rollback', ?, '测试', 'active', NULL, ?, ?)",
            (old_user_id, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO community_ugc_follows VALUES (?, ?, ?)",
            (old_user_id, other_user_id, timestamp),
        )
        connection.execute(
            "INSERT INTO community_ugc_reports VALUES "
            "('report-rollback', ?, 'post', 'post-rollback', '测试', NULL, 'open', ?, ?)",
            (old_user_id, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO community_favorites VALUES (?, 'editorial-rollback', '{}', ?, ?)",
            (old_user_id, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO user_sessions "
            "(id, user_id, token_hash, created_at, expires_at, revoked_at, last_seen_at) "
            "VALUES ('session-rollback', ?, ?, ?, '2099-01-01T00:00:00+00:00', NULL, ?)",
            (old_user_id, "a" * 64, timestamp, timestamp),
        )
        connection.execute(
            "CREATE TRIGGER fail_community_user_reassign "
            "BEFORE UPDATE OF user_id ON users WHEN OLD.user_id = 'legacy-community-user' "
            "BEGIN SELECT RAISE(ABORT, 'forced user update failure'); END"
        )

    with pytest.raises(sqlite3.DatabaseError, match="forced user update failure"):
        repository.reassign_user_id(old_user_id, new_user_id, timestamp)

    assert repository.get_user(old_user_id) is not None
    assert repository.get_user(new_user_id) is None
    with repository.connect() as connection:
        checks = (
            ("community_ugc_posts", "owner_user_id"),
            ("community_ugc_likes", "user_id"),
            ("community_ugc_saves", "user_id"),
            ("community_ugc_comments", "author_user_id"),
            ("community_ugc_reports", "reporter_user_id"),
            ("community_favorites", "user_id"),
            ("user_sessions", "user_id"),
        )
        for table, column in checks:
            assert connection.execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE {column} = ?",
                (old_user_id,),
            ).fetchone()["total"] == 1
        assert connection.execute(
            "SELECT COUNT(*) AS total FROM community_ugc_follows "
            "WHERE follower_user_id = ? OR followed_user_id = ?",
            (old_user_id, old_user_id),
        ).fetchone()["total"] == 1


def test_reassign_user_id_serializes_with_legacy_community_favorite_write(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "community-favorite-race.db"
    repository = _migrated_repository(db_path)
    favorites = OrderService(db_path)
    old_user_id = "legacy-favorite-race"
    new_user_id = "100000000004"
    _upsert_test_user(repository, old_user_id)
    favorites.save_community_favorite(
        {"user_id": old_user_id, "post_id": "seed", "item": {"title": "迁移前"}}
    )
    entered = threading.Event()
    release = threading.Event()
    original_merge = repository._merge_community_favorites

    def paused_merge(connection, old_id, new_id):
        original_merge(connection, old_id, new_id)
        entered.set()
        assert release.wait(timeout=5)

    monkeypatch.setattr(repository, "_merge_community_favorites", paused_merge)
    with ThreadPoolExecutor(max_workers=2) as executor:
        migration = executor.submit(
            repository.reassign_user_id,
            old_user_id,
            new_user_id,
            "2026-07-17T03:00:00+00:00",
        )
        assert entered.wait(timeout=5)
        stale_write = executor.submit(
            favorites.save_community_favorite,
            {"user_id": old_user_id, "post_id": "late", "item": {"title": "竞态写入"}},
        )
        release.set()
        assert migration.result(timeout=5)["user_id"] == new_user_id
        with pytest.raises(ValueError, match="用户不存在"):
            stale_write.result(timeout=5)

    assert [item["post_id"] for item in favorites.list_community_favorites(new_user_id)] == [
        "seed"
    ]
    assert favorites.list_community_favorites(old_user_id) == []


def test_reassigned_bearer_session_authenticates_and_writes_as_new_user(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "community-session-reassign.db"
    repository = _migrated_repository(db_path)
    old_user_id = "legacy-session-user"
    new_user_id = "100000000003"
    _upsert_test_user(repository, old_user_id)
    sessions = UserSessionService(db_path)
    session = sessions.create(old_user_id)
    service = CommunityUGCService(db_path)
    monkeypatch.setattr(api_module, "community_ugc_service", service)
    monkeypatch.setattr(user_sessions_module, "session_service", sessions)
    monkeypatch.setenv("COMMUNITY_UGC_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_UGC_WRITES_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_MODERATION_REQUIRED", "true")

    repository.reassign_user_id(
        old_user_id, new_user_id, "2026-07-17T02:00:00+00:00"
    )

    principal = sessions.authenticate(session["access_token"])
    assert principal is not None
    assert principal.user_id == new_user_id
    with pytest.raises(CommunityNotFound, match="用户不存在"):
        service.create_post(
            old_user_id,
            {"title": "旧主体", "content": "不得继续写入", "image_urls": [], "tags": []},
        )

    app.dependency_overrides.pop(require_current_user, None)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/community/posts",
            headers={"Authorization": f"Bearer {session['access_token']}"},
            json={"title": "迁移后会话", "content": "只允许写入新主体"},
        )

    assert created.status_code == 201, created.text
    assert created.json()["data"]["author"]["user_id"] == new_user_id
    with repository.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) AS total FROM community_ugc_posts WHERE owner_user_id = ?",
            (old_user_id,),
        ).fetchone()["total"] == 0
