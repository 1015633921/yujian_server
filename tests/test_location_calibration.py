from __future__ import annotations

from pathlib import Path

from app.energy import EnergyCalculator
from app.locations import LOCATION_DATA_VERSION, LOCATION_RECORDS, picker_location_code, resolve_location
from app.schemas import AssessmentRequest
from app.service import AssessmentService
from scripts.build_location_dataset import read_picker_entries


def request_for_location(province: str, city: str, **overrides) -> AssessmentRequest:
    payload = {
        "user_id": "location-calibration-test",
        "name": "地点校准测试",
        "birthday": "1995-08-16",
        "birth_time": "09:30",
        "birth_time_unknown": False,
        "birth_place": city,
        "birth_place_path": f"{province}/{city}",
        "location_code": picker_location_code(province, city),
        "core_wishes": ["健康护身/保持专注"],
    }
    payload.update(overrides)
    return AssessmentRequest(**payload)


def test_versioned_dataset_covers_every_current_picker_city_once():
    picker_entries = read_picker_entries(Path("miniprogram/pages/assessment/assessment.js"))
    picker_paths = {(entry.province, entry.city) for entry in picker_entries}
    dataset_paths = {(record.province, record.city) for record in LOCATION_RECORDS}

    assert LOCATION_DATA_VERSION == "geonames-cn-city-seat-v1"
    assert len(picker_entries) == len(LOCATION_RECORDS) == 378
    assert dataset_paths == picker_paths
    assert len({record.code for record in LOCATION_RECORDS}) == len(LOCATION_RECORDS)
    assert all(record.precision == "city-seat" for record in LOCATION_RECORDS)


def test_city_paths_resolve_without_same_name_ambiguity():
    samples = {
        ("河北省", "石家庄市"): ("Asia/Shanghai", "河北省·石家庄市"),
        ("新疆维吾尔自治区", "可克达拉市"): ("Asia/Shanghai", "新疆维吾尔自治区·可克达拉市"),
        ("台湾省", "台北市"): ("Asia/Taipei", "台湾省·台北市"),
        ("香港特别行政区", "香港特别行政区"): ("Asia/Hong_Kong", "香港特别行政区"),
        ("澳门特别行政区", "澳门特别行政区"): ("Asia/Macau", "澳门特别行政区"),
    }
    for (province, city), (timezone, resolved_name) in samples.items():
        record = resolve_location(None, f"{province}/{city}")
        assert record is not None
        assert record.timezone == timezone
        assert record.resolved_name == resolved_name
        assert resolve_location(None, city) == record


def test_new_client_picker_path_and_code_complete_calibration():
    result = EnergyCalculator().calculate_true_solar_time(request_for_location("河北省", "石家庄市"))

    assert result["calibration_status"] == "applied"
    assert result["resolved_location_name"] == "河北省·石家庄市"
    assert result["resolved_location_precision"] == "city-seat"
    assert result["location_data_version"] == LOCATION_DATA_VERSION
    assert result["timezone"] == "Asia/Shanghai"
    assert result["calibrated_time"]


def test_mismatched_picker_code_or_city_is_never_used_for_calibration():
    wrong_code = EnergyCalculator().calculate_true_solar_time(
        request_for_location("河北省", "石家庄市", location_code="cn:city:v1:not-the-picker-code")
    )
    wrong_city = EnergyCalculator().calculate_true_solar_time(
        request_for_location("河北省", "石家庄市", birth_place="成都市")
    )

    assert wrong_code["calibration_status"] == "invalid_location"
    assert wrong_code["calibration_reason_code"] == "location_code_does_not_match_picker_path"
    assert wrong_city["calibration_status"] == "invalid_location"
    assert wrong_city["calibration_reason_code"] == "birth_place_does_not_match_picker_path"
    assert wrong_code["calibrated_time"] is None
    assert wrong_city["calibrated_time"] is None


def test_historical_timezone_offset_sets_the_correct_standard_meridian():
    result = EnergyCalculator().calculate_true_solar_time(
        request_for_location("上海市", "上海市", birthday="1990-07-01")
    )

    # China used daylight saving time in 1990. The IANA historical offset is
    # UTC+09:00, so true-solar correction must use 135° rather than hard-coding
    # the modern 120° standard meridian.
    assert result["calibration_status"] == "applied"
    assert result["utc_offset_minutes"] == 540
    assert result["standard_meridian_longitude"] == 135.0
    assert result["longitude_correction_minutes"] < -50


def test_unknown_birth_time_never_fabricates_a_true_solar_time():
    result = EnergyCalculator().calculate_true_solar_time(
        request_for_location("四川省", "成都市", birth_time_unknown=True)
    )

    assert result["calibration_status"] == "not_required"
    assert result["calibrated_time"] is None
    assert result["resolved_location_name"] == "四川省·成都市"


def test_service_snapshot_keeps_the_full_picker_path_and_calibration_version(tmp_path):
    service = AssessmentService(tmp_path / "location-calibration.db")
    result, cache_hit = service.calculate_energy(
        request_for_location("上海市", "上海市", birthday="1990-07-01")
    )

    assert cache_hit is False
    assert result["input_summary"]["birth_place_path"] == "上海市/上海市"
    assert result["input_summary"]["location_code"] == picker_location_code("上海市", "上海市")
    assert result["solar_time"]["calibration_version"] == "true-solar-time-v3-city-seat-timezone"
    assert result["solar_time"]["location_data_version"] == LOCATION_DATA_VERSION
