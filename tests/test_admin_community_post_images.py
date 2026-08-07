from __future__ import annotations

from app.admin_service import AdminService


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
