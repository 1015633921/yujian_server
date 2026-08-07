from app.admin_service import AdminService


def test_daily_rule_history_keeps_publish_context_and_restores_snapshot(tmp_path, monkeypatch):
    service = AdminService(tmp_path / "daily-rules-history.db")
    actor = {"role": "admin", "username": "ops_01"}
    setting_connections = []
    original_save_setting = service.save_setting

    def record_save_setting(setting_key, value, updated_at, connection=None):
        setting_connections.append(connection)
        return original_save_setting(setting_key, value, updated_at, connection)

    monkeypatch.setattr(service, "save_setting", record_save_setting)

    first = service.daily_energy_rules()
    first_rules = first["rules"]
    first_version = first["rules_version"]

    changed_rules = {
        **first_rules,
        "scoring": {**first_rules["scoring"], "starter_base": 71},
    }
    published = service.save_daily_energy_rules(
        {"rules": changed_rules, "change_note": "提高基础模式分"}, actor
    )
    published_version = published["rules_version"]
    assert published_version != first_version
    assert setting_connections[-2] is setting_connections[-1]
    assert setting_connections[-1] is not None

    history = service.daily_energy_rules()["history"]
    old_snapshot = next(item for item in history if item["version"] == first_version)
    assert old_snapshot["current"] is False
    assert history[0]["current"] is True

    restored = service.save_daily_energy_rules(
        {"rules": {}, "restore_version": first_version, "change_note": "回退基础分"}, actor
    )
    assert restored["rules_version"] == first_version
    assert restored["rules"]["scoring"]["starter_base"] == first_rules["scoring"]["starter_base"]
    assert any(item["version"] == published_version for item in restored["history"])
