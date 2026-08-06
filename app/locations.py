from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Asia/Shanghai"
CALIBRATION_VERSION = "true-solar-time-v3-city-seat-timezone"
_DATASET_PATH = Path(__file__).with_name("data") / "china_city_centers_v1.json"


@dataclass(frozen=True)
class LocationRecord:
    """A reviewed city-centre coordinate from the bundled source dataset."""

    code: str
    display_name: str
    aliases: tuple[str, ...]
    longitude: float
    latitude: float
    province: str
    city: str
    timezone: str
    precision: str
    territory: str

    @property
    def resolved_name(self) -> str:
        """Human-readable province/city path without duplicating municipalities."""

        if normalize_location_name(self.province) == normalize_location_name(self.city):
            return self.city
        return f"{self.province}·{self.city}"


def normalize_location_name(value: str | None) -> str:
    """Normalize a picker path or encoded client location code for lookup."""

    raw = unquote(str(value or "")).strip()
    return "".join(raw.replace("/", "").replace("·", "").split())


def _canonical_records_hash(records: list[dict]) -> str:
    rendered = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _required_text(raw: dict, field: str) -> str:
    value = str(raw.get(field) or "").strip()
    if not value:
        raise ValueError(f"Location dataset record has no {field}")
    return value


def _load_dataset() -> tuple[str, tuple[LocationRecord, ...]]:
    try:
        document = json.loads(_DATASET_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Location dataset cannot be read: {_DATASET_PATH}") from exc

    records_raw = document.get("records")
    if document.get("schema_version") != 1 or not isinstance(records_raw, list) or not records_raw:
        raise RuntimeError("Location dataset schema is invalid")
    expected_hash = str(document.get("records_sha256") or "")
    if expected_hash != _canonical_records_hash(records_raw):
        raise RuntimeError("Location dataset integrity check failed")

    coverage = document.get("coverage") or {}
    if coverage.get("record_count") != len(records_raw):
        raise RuntimeError("Location dataset coverage count is invalid")

    seen_codes: set[str] = set()
    seen_paths: set[tuple[str, str]] = set()
    records: list[LocationRecord] = []
    for raw in records_raw:
        if not isinstance(raw, dict):
            raise RuntimeError("Location dataset contains a non-object record")
        code = _required_text(raw, "code").lower()
        province = _required_text(raw, "province")
        city = _required_text(raw, "city")
        display_name = _required_text(raw, "display_name")
        timezone = _required_text(raw, "timezone")
        territory = _required_text(raw, "territory")
        precision = _required_text(raw, "precision")
        aliases_raw = raw.get("aliases")
        if not isinstance(aliases_raw, list):
            raise RuntimeError(f"Location dataset aliases are invalid for {code}")
        aliases = tuple(dict.fromkeys(_required_text({"alias": alias}, "alias") for alias in aliases_raw))
        if not aliases:
            raise RuntimeError(f"Location dataset aliases are empty for {code}")
        try:
            longitude = float(raw["longitude"])
            latitude = float(raw["latitude"])
            ZoneInfo(timezone)
        except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError) as exc:
            raise RuntimeError(f"Location dataset coordinate or timezone is invalid for {code}") from exc
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise RuntimeError(f"Location dataset WGS84 coordinate is invalid for {code}")
        if precision != "city-seat":
            raise RuntimeError(f"Location dataset precision is invalid for {code}")
        path_key = (normalize_location_name(province), normalize_location_name(city))
        if code in seen_codes or path_key in seen_paths:
            raise RuntimeError(f"Location dataset contains duplicate record {code}")
        seen_codes.add(code)
        seen_paths.add(path_key)
        records.append(
            LocationRecord(
                code=code,
                display_name=display_name,
                aliases=aliases,
                longitude=longitude,
                latitude=latitude,
                province=province,
                city=city,
                timezone=timezone,
                precision=precision,
                territory=territory,
            )
        )

    version = _required_text(document, "dataset_version")
    return version, tuple(records)


LOCATION_DATA_VERSION, LOCATION_RECORDS = _load_dataset()
_BY_CODE = {record.code: record for record in LOCATION_RECORDS}
_BY_NAME: dict[str, tuple[LocationRecord, ...]] = {}
_name_candidates: dict[str, list[LocationRecord]] = defaultdict(list)
for _record in LOCATION_RECORDS:
    for _name in (_record.display_name, _record.province + _record.city, *_record.aliases):
        _normalized = normalize_location_name(_name)
        if _normalized and _record not in _name_candidates[_normalized]:
            _name_candidates[_normalized].append(_record)
_BY_NAME = {name: tuple(records) for name, records in _name_candidates.items()}

# Preserve compatibility for requests from versions that emitted the former eleven
# project codes.  These aliases resolve to the new dataset records, never to a
# hard-coded coordinate.
_LEGACY_CODE_TO_CITY = {
    "cn:beijing": "北京市",
    "cn:shanghai": "上海市",
    "cn:guangzhou": "广州市",
    "cn:shenzhen": "深圳市",
    "cn:chengdu": "成都市",
    "cn:chongqing": "重庆市",
    "cn:hangzhou": "杭州市",
    "cn:wuhan": "武汉市",
    "cn:xian": "西安市",
    "cn:nanjing": "南京市",
    "cn:lanzhou": "兰州市",
}


def _unique_name_match(value: str | None) -> LocationRecord | None:
    candidates = _BY_NAME.get(normalize_location_name(value), ())
    return candidates[0] if len(candidates) == 1 else None


def picker_location_code(province: str, city: str) -> str:
    """Return the deterministic compact code emitted by the mini-program picker."""

    value = f"{province.strip()}/{city.strip()}"
    value_hash = 2166136261
    for character in value:
        # Mirrors JavaScript's charCodeAt + Math.imul FNV-1a implementation.
        value_hash ^= ord(character)
        value_hash = (value_hash * 16777619) & 0xFFFFFFFF
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    encoded = "0" if value_hash == 0 else ""
    while value_hash:
        value_hash, remainder = divmod(value_hash, 36)
        encoded = alphabet[remainder] + encoded
    return f"cn:city:v1:{encoded}"


def resolve_location(location_code: str | None, display_name: str | None) -> LocationRecord | None:
    """Resolve a stable dataset code or a fully qualified picker path.

    The current mini-program sends the readable province/city path separately
    and a compact `cn:city:v1:` consistency key. Older encoded `cn:city:` paths
    remain readable for compatibility. Neither is a client coordinate; returned
    coordinates always come from this bundled dataset.
    """

    code = str(location_code or "").strip().lower()
    if code:
        direct = _BY_CODE.get(code)
        if direct:
            return direct
        legacy_city = _LEGACY_CODE_TO_CITY.get(code)
        if legacy_city:
            return _unique_name_match(legacy_city)
        prefix = "cn:city:"
        if code.startswith(prefix):
            return _unique_name_match(unquote(code[len(prefix):]))
        return None
    return _unique_name_match(display_name)
