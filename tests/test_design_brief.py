from __future__ import annotations

from app.design_brief import BRIEF_RULE_VERSION, build_design_brief


def report_summary(*, score: int = 31) -> dict:
    return {
        "core_conclusion": {"title": "土元素倾向鲜明，金元素适合温柔调和", "summary": "稳定感明显。"},
        "ranking": {"dominant": "土", "secondary": "火", "lowest": "金"},
        "balance": {"score": score, "label": "倾向明显"},
        "adjustment_strategy": [
            {"role": "主要调整", "element": "金"},
            {"role": "辅助调整", "element": "水"},
            {"role": "少量点缀", "element": "木"},
        ],
        "core_wishes": ["健康护身/保持专注"],
        "style_guidance": {"recommended_texture": "温润、柔和、有质感", "reduce": "大面积黄棕、过密排列与厚重堆叠"},
        "mood_analysis": {"name": "海盐蓝白"},
        "chakra_analysis": {"primary_chakra_name": "心轮"},
        "mbti_analysis": {"selected": True, "type": "INFP"},
        "zodiac_analysis": {"name": "摩羯座"},
    }


def request() -> dict:
    return {
        "wrist_size_cm": 15.5,
        "bead_size_mm": 8,
        "budget": "300–500 元",
        "style_preference": "清透自然",
        "color_preference": "蓝白、低饱和、不要深色",
        "accessory_preference": "适量点缀",
        "wear_scene": "日常佩戴",
        "preference_confirmed": True,
        "note": "希望整体轻盈",
    }


def test_design_brief_turns_report_into_explainable_design_language():
    brief = build_design_brief(
        report_summary(), request(), report_id="report-1", report_code="RPT-20260806-001", report_version=2
    )

    assert brief["schema_version"] == 1
    assert brief["rule_version"] == BRIEF_RULE_VERSION
    assert brief["status"] == "ready"
    assert brief["lineage"]["report_code"] == "RPT-20260806-001"
    assert brief["intervention"]["label"] == "重点调和"
    assert "土的稳定温润" in brief["design_goal"]["title"]
    assert [role["element"] for role in brief["material_roles"]] == ["金", "水", "木"]
    assert {item["key"] for item in brief["palette"]["base"]} == {"blue", "white"}
    assert {item["key"] for item in brief["palette"]["avoid"]} == {"black"}
    assert brief["structure"]["dominant_note"].startswith("土代表已有")
    assert any(item["source"] == "用户色彩偏好" for item in brief["source_evidence"])
    assert any(item["label"] == "主导元素与调整方向不同" for item in brief["warnings"])
    assert brief["preferences"]["confirmed"] is True
    assert brief["preferences"]["source"] == "用户已确认"
    assert "生日" not in str(brief)
    assert "出生地" not in str(brief)


def test_design_brief_balance_bands_control_intervention_not_material_names():
    expected = {
        54: "重点调和",
        55: "明确调和",
        69: "明确调和",
        70: "轻度调和",
        84: "轻度调和",
        85: "审美优先",
    }
    for score, label in expected.items():
        brief = build_design_brief(report_summary(score=score), request())
        assert brief["intervention"]["label"] == label
        assert "水晶" not in brief["intervention"]["reason"]


def test_design_brief_is_safe_when_report_or_optional_signals_are_missing():
    brief = build_design_brief({}, {"wrist_size_cm": 16, "bead_size_mm": 10})

    assert brief["status"] == "partial"
    assert brief["hard_constraints"][0]["value"] == "16 cm"
    assert brief["hard_constraints"][1]["value"] == "10 mm"
    assert brief["material_roles"][0]["element"] == ""
    assert any(item["label"] == "测算依据不完整" for item in brief["warnings"])


def test_design_brief_marks_old_or_unconfirmed_preferences_for_designer_review():
    old_request = request()
    old_request.pop("preference_confirmed")

    brief = build_design_brief(report_summary(), old_request)

    assert brief["preferences"]["confirmed"] is False
    assert "发布前请确认" in brief["preferences"]["source"]
    assert any(item["label"] == "配饰或场景待确认" for item in brief["warnings"])
