from __future__ import annotations

from app.admin_service import AdminService
from app.repository import AssessmentRepository


def test_admin_energy_detail_reads_assessment_daily_energy_and_checkin(tmp_path):
    db_path = tmp_path / "admin-energy-detail.db"
    repository = AssessmentRepository(db_path)
    repository.save(
        {
            "assessment_id": "assessment-detail-1",
            "created_at": "2026-08-07T10:00:00+08:00",
            "input_summary": {"user_id": "user-detail-1", "name": "小涧", "core_wish": "安定"},
            "final_energy_profile": {"金": 12, "木": 18, "水": 28, "火": 15, "土": 27},
            "energy_breakdown": {"bazi": {"水": 10}},
            "strongest_element": "水",
            "weakest_element": "金",
            "energy_keywords": ["喜水", {"label": "稳住节奏"}],
            "seasonal_energy": {"title": "秋日收敛"},
            "interpretation": "优先稳定节奏。",
            "primary_crystal": {"name": "海蓝宝"},
            "supporting_crystals": [{"name": "白水晶"}],
            "bracelet_plan": {"layout": []},
            "recommendation_copy": "以海蓝宝作为主石。",
            "care_tips": ["避免碰撞"],
            "disclaimer": "传统文化体验。",
        },
        "detail-fingerprint",
    )
    repository.save_daily_energy(
        {
            "user_id": "user-detail-1",
            "date": "2026-08-07",
            "mode": "daily",
            "assessment_id": "assessment-detail-1",
            "calculated_at": "2026-08-07T10:01:00+08:00",
            "title": "温柔启动",
            "score": 82,
            "lucky_color": "蓝色",
            "recommended_stone": "海蓝宝",
            "energy_profile": {"水": 28},
            "energy_keywords": ["喜水"],
            "advice": "先做一件小事。",
            "lucky_time": "09:00-11:00",
        }
    )
    repository.save_checkin(
        {
            "user_id": "user-detail-1",
            "date": "2026-08-07",
            "mood": 4,
            "sleep": 3,
            "stress": 2,
            "created_at": "2026-08-07T08:00:00+08:00",
            "updated_at": "2026-08-07T08:00:00+08:00",
        }
    )
    service = AdminService(db_path)

    assessment = service.get_assessment_detail("assessment-detail-1")
    daily = service.get_daily_energy_detail("user-detail-1", "2026-08-07")
    checkin = service.get_checkin_detail("user-detail-1", "2026-08-07")

    assert assessment["energy"]["profile"]["水"] == 28
    assert assessment["formula"]["tags"][0]["name"] == "海蓝宝"
    assert assessment["recommendation"]["supporting_crystals"][0]["name"] == "白水晶"
    assert daily["recommended_stone"] == "海蓝宝"
    assert daily["advice"] == "先做一件小事。"
    assert checkin["mood"] == 4
