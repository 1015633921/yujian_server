from __future__ import annotations

from dataclasses import dataclass


LOCATION_DATA_VERSION = "project-built-in-cities-v1"
CALIBRATION_VERSION = "true-solar-time-v2"
DEFAULT_TIMEZONE = "Asia/Shanghai"


@dataclass(frozen=True)
class LocationRecord:
    code: str
    display_name: str
    aliases: tuple[str, ...]
    longitude: float
    latitude: float
    timezone: str = DEFAULT_TIMEZONE


# These coordinates already existed in app.energy before P1-B. No new coordinates
# are inferred or downloaded here.
LOCATION_RECORDS = (
    LocationRecord("cn:beijing", "北京市", ("北京", "北京市"), 116.4074, 39.9042),
    LocationRecord("cn:shanghai", "上海市", ("上海", "上海市"), 121.4737, 31.2304),
    LocationRecord("cn:guangzhou", "广州市", ("广州", "广州市"), 113.2644, 23.1291),
    LocationRecord("cn:shenzhen", "深圳市", ("深圳", "深圳市"), 114.0579, 22.5431),
    LocationRecord("cn:chengdu", "成都市", ("成都", "成都市", "四川省成都市"), 104.0665, 30.5723),
    LocationRecord("cn:chongqing", "重庆市", ("重庆", "重庆市"), 106.5516, 29.5630),
    LocationRecord("cn:hangzhou", "杭州市", ("杭州", "杭州市"), 120.1551, 30.2741),
    LocationRecord("cn:wuhan", "武汉市", ("武汉", "武汉市"), 114.3054, 30.5931),
    LocationRecord("cn:xian", "西安市", ("西安", "西安市"), 108.9398, 34.3416),
    LocationRecord("cn:nanjing", "南京市", ("南京", "南京市"), 118.7969, 32.0603),
    LocationRecord("cn:lanzhou", "兰州市", ("兰州", "兰州市", "甘肃省兰州市"), 103.8343, 36.0611),
)


def normalize_location_name(value: str | None) -> str:
    return "".join(str(value or "").strip().split())


def resolve_location(location_code: str | None, display_name: str | None) -> LocationRecord | None:
    code = str(location_code or "").strip().lower()
    if code:
        for record in LOCATION_RECORDS:
            if record.code == code:
                return record
        return None

    name = normalize_location_name(display_name)
    if not name:
        return None
    exact = [
        record
        for record in LOCATION_RECORDS
        if name == normalize_location_name(record.display_name)
        or name in {normalize_location_name(alias) for alias in record.aliases}
    ]
    return exact[0] if len(exact) == 1 else None
