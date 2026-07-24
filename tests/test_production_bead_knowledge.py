from scripts.enrich_production_bead_knowledge import (
    PROFILE_SPECS,
    VALID_OPTIONS,
    build_profiles,
)


def test_all_production_bead_profiles_are_complete_and_use_supported_options():
    profiles = build_profiles()

    assert len(profiles) == 24
    assert set(profiles) == set(PROFILE_SPECS)
    for code, profile in profiles.items():
        assert profile["primary_element"] in VALID_OPTIONS["elements"], code
        assert set(profile["secondary_elements"]) <= VALID_OPTIONS["elements"], code
        assert set(profile["effects"]) <= VALID_OPTIONS["effects"], code
        assert set(profile["wish_pools"]) <= VALID_OPTIONS["wishes"], code
        assert profile["color_family"] in VALID_OPTIONS["colors"], code
        assert set(profile["mood_tags"]) <= VALID_OPTIONS["moods"], code
        assert set(profile["visual_tags"]) <= VALID_OPTIONS["visual"], code
        assert set(profile["allowed_roles"]) <= VALID_OPTIONS["roles"], code
        assert set(profile["match_rules"]) <= VALID_OPTIONS["rules"], code
        assert set(profile["care_tags"]) <= VALID_OPTIONS["care"], code
        assert profile["story"].count("。") >= 3, code
        assert "传统文化和设计灵感参考" in profile["story"], code
        assert profile["conflict_codes"] == [], code


def test_high_visual_weight_beads_have_density_or_balance_rules():
    profiles = build_profiles()

    for code in (
        "rabbit_hair_quartz",
        "gold_rutilated_quartz",
        "titanium_quartz",
        "black_rutilated_quartz",
        "c58e5e42bc727230",
    ):
        rules = set(profiles[code]["match_rules"])
        assert "avoid_dense" in rules
        assert "needs_color_balance" in rules
