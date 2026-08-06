#!/usr/bin/env python3
"""Build the versioned city-seat coordinate dataset used for birth-place calibration.

The mini-program currently asks users to choose a province and city/prefecture.  This
script turns exactly that picker list into a static, auditable WGS84 dataset.  It is a
build-time utility only: the application never sends a user's birth place to an
external map service at runtime.

Input sources
-------------
* GeoNames country dumps (CN, TW, HK, MO), CC BY 4.0:
  https://download.geonames.org/export/dump/
* Five recently established Xinjiang county-level cities that are absent from the
  downloaded GeoNames snapshot use the public Wikidata P625 coordinate statement
  (CC0).  They are declared explicitly below so they cannot be selected silently.

The generator intentionally fails if a picker entry cannot be resolved or if the
best GeoNames match is still ambiguous.  That makes an update to the picker or source
data a reviewable data change instead of a partial calibration release.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DATASET_VERSION = "geonames-cn-city-seat-v1"
SCHEMA_VERSION = 1
DEFAULT_OUTPUT = Path("app/data/china_city_centers_v1.json")
DEFAULT_PICKER = Path("miniprogram/pages/assessment/assessment.js")
SOURCE_COUNTRIES = ("CN", "TW", "HK", "MO")

# The current picker is province/city level.  All administrative territories use
# their territory-specific IANA zone rather than inheriting Asia/Shanghai by default.
TERRITORY_BY_PROVINCE = {
    "台湾省": "TW",
    "香港特别行政区": "HK",
    "澳门特别行政区": "MO",
}
TIMEZONE_BY_TERRITORY = {
    "CN": "Asia/Shanghai",
    "TW": "Asia/Taipei",
    "HK": "Asia/Hong_Kong",
    "MO": "Asia/Macau",
}

# GeoNames uses a mix of English canonical labels, simplified Chinese aliases and
# traditional Chinese aliases.  This intentionally small conversion table covers the
# characters used by the existing picker; all other source aliases remain untouched.
TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "臺": "台",
        "灣": "湾",
        "義": "义",
        "東": "东",
        "西": "西",
        "廣": "广",
        "寧": "宁",
        "內": "内",
        "壯": "壮",
        "維": "维",
        "爾": "尔",
        "烏": "乌",
        "魯": "鲁",
        "齊": "齐",
        "龍": "龙",
        "蘭": "兰",
        "遼": "辽",
        "陝": "陕",
        "慶": "庆",
        "貴": "贵",
        "雲": "云",
        "蘇": "苏",
        "晉": "晋",
        "滄": "沧",
        "濱": "滨",
        "鄉": "乡",
        "縣": "县",
        "區": "区",
        "長": "长",
        "萬": "万",
        "樂": "乐",
        "陽": "阳",
        "鶴": "鹤",
        "綏": "绥",
        "興": "兴",
        "濟": "济",
        "濰": "潍",
        "棗": "枣",
        "鄭": "郑",
        "駐": "驻",
        "開": "开",
        "許": "许",
        "濮": "濮",
        "荊": "荆",
        "隨": "随",
        "鹹": "咸",
        "嶽": "岳",
        "婁": "娄",
        "懷": "怀",
        "欽": "钦",
        "賀": "贺",
        "崇": "崇",
        "瓊": "琼",
        "儋": "儋",
        "澄": "澄",
        "陵": "陵",
        "瀘": "泸",
        "綿": "绵",
        "達": "达",
        "資": "资",
        "涼": "凉",
        "銅": "铜",
        "畢": "毕",
        "麗": "丽",
        "臨": "临",
        "紅": "红",
        "傣": "傣",
        "薩": "萨",
        "喀": "喀",
        "寶": "宝",
        "漢": "汉",
        "榆": "榆",
        "隴": "陇",
        "衛": "卫",
        "圖": "图",
        "庫": "库",
        "雙": "双",
        "剋": "克",
        "楊": "杨",
    }
)

# Do not reduce a target all the way to a generic one-character fragment.  Variants
# exist only to bridge labels such as "海口市"/"海口" and "兴安盟"/"兴安".
PLACE_SUFFIXES = (
    "特别行政区",
    "维吾尔自治区",
    "壮族自治区",
    "回族自治区",
    "藏族自治州",
    "蒙古族自治州",
    "哈萨克自治州",
    "柯尔克孜自治州",
    "土家族苗族自治州",
    "布依族苗族自治州",
    "苗族侗族自治州",
    "哈尼族彝族自治州",
    "傣族景颇族自治州",
    "傈僳族自治州",
    "白族自治州",
    "羌族自治州",
    "彝族自治州",
    "朝鲜族自治州",
    "黎族自治县",
    "黎族苗族自治县",
    "黎族苗族自治县",
    "蒙古族藏族自治州",
    "蒙古族",
    "自治区",
    "自治州",
    "地区",
    "林区",
    "省",
    "市",
    "县",
    "盟",
)

# Lower numbers are preferred.  Settlements are normally a better "city-seat"
# approximation than an administrative-area centroid; administrative records remain
# valid fallbacks for prefectures and county-level entries with no settlement record.
FEATURE_PRIORITY = {
    "PPLC": 0,
    "PPLA": 1,
    "PPLA2": 2,
    "PPLA3": 3,
    "PPLA4": 4,
    "PPLG": 5,
    "PPL": 6,
    "ADM2": 7,
    "ADM3": 8,
    "ADM1": 9,
}

# GeoNames' current country dumps do not contain these five newer Xinjiang city
# records.  Each value is a manually reviewed Wikidata coordinate statement (P625).
# The script still requires an explicit entry rather than accepting an unmatched
# picker option.  All remain city-seat precision, not a user's exact birth address.
MANUAL_WIKIDATA_OVERRIDES: dict[tuple[str, str], dict[str, Any]] = {
    ("新疆维吾尔自治区", "铁门关市"): {
        "wikidata_id": "Q5103019",
        "latitude": 41.820000,
        "longitude": 85.653000,
    },
    ("新疆维吾尔自治区", "双河市"): {
        "wikidata_id": "Q10930847",
        "latitude": 44.840000,
        "longitude": 82.351700,
    },
    ("新疆维吾尔自治区", "可克达拉市"): {
        "wikidata_id": "Q18651998",
        "latitude": 43.934060,
        "longitude": 80.998160,
    },
    ("新疆维吾尔自治区", "新星市"): {
        "wikidata_id": "Q105300298",
        "latitude": 42.795278,
        "longitude": 93.746389,
    },
    ("新疆维吾尔自治区", "白杨市"): {
        "wikidata_id": "Q116265658",
        "latitude": 46.724444,
        "longitude": 82.895833,
    },
}


@dataclass(frozen=True)
class PickerEntry:
    province: str
    city: str
    territory: str


@dataclass(frozen=True)
class GeoNamesRecord:
    geoname_id: str
    name: str
    aliases: frozenset[str]
    latitude: float
    longitude: float
    feature_code: str
    country_code: str
    admin1_code: str
    population: int
    timezone: str
    modified_at: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_name(value: str | None) -> str:
    """Normalize a source or picker name without transliterating non-Chinese names."""

    return "".join(str(value or "").strip().translate(TRADITIONAL_TO_SIMPLIFIED).split())


def name_variants(value: str) -> frozenset[str]:
    normalized = normalize_name(value)
    variants = {normalized}
    for suffix in PLACE_SUFFIXES:
        if normalized.endswith(suffix) and len(normalized) > len(suffix) + 1:
            variants.add(normalized[: -len(suffix)])
    return frozenset(item for item in variants if item)


def read_picker_entries(path: Path) -> list[PickerEntry]:
    source = path.read_text(encoding="utf-8")
    match = re.search(
        r"const\s+REGION_OPTIONS\s*=\s*(\[[\s\S]*?\])\s*;\s*\nconst\s+REGION_PROVINCES",
        source,
    )
    if not match:
        raise ValueError(f"Unable to find REGION_OPTIONS in {path}")

    # REGION_OPTIONS is deliberately a simple JS object literal.  Quote its two
    # property keys then let Python's safe literal parser validate the remaining data.
    literal = re.sub(
        r"([,{]\s*)(province|cities)\s*:",
        r"\1'\2':",
        match.group(1),
    )
    try:
        options = ast.literal_eval(literal)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"REGION_OPTIONS is not a supported literal: {exc}") from exc

    if not isinstance(options, list):
        raise ValueError("REGION_OPTIONS must be a list")
    entries: list[PickerEntry] = []
    seen: set[tuple[str, str]] = set()
    for option in options:
        if not isinstance(option, dict):
            raise ValueError("Every REGION_OPTIONS item must be an object")
        province = str(option.get("province") or "").strip()
        cities = option.get("cities")
        if not province or not isinstance(cities, list) or not cities:
            raise ValueError(f"Invalid picker option: {option!r}")
        territory = TERRITORY_BY_PROVINCE.get(province, "CN")
        for city_value in cities:
            city = str(city_value or "").strip()
            key = (province, city)
            if not city or key in seen:
                raise ValueError(f"Duplicate or empty picker entry: {key!r}")
            seen.add(key)
            entries.append(PickerEntry(province=province, city=city, territory=territory))
    if not entries:
        raise ValueError("REGION_OPTIONS has no cities")
    return entries


def parse_geonames_row(row: list[str]) -> GeoNamesRecord | None:
    if len(row) < 19:
        return None
    feature_class = row[6]
    feature_code = row[7]
    if feature_class not in {"P", "A"}:
        return None
    if feature_code not in FEATURE_PRIORITY and feature_code != "ADM1":
        return None
    aliases = {
        normalize_name(row[1]),
        normalize_name(row[2]),
        *(normalize_name(alias) for alias in row[3].split(",")),
    }
    aliases.discard("")
    try:
        return GeoNamesRecord(
            geoname_id=row[0],
            name=row[1],
            aliases=frozenset(aliases),
            latitude=float(row[4]),
            longitude=float(row[5]),
            feature_code=feature_code,
            country_code=row[8],
            admin1_code=row[10],
            population=int(row[14] or 0),
            timezone=row[17],
            modified_at=row[18],
        )
    except (TypeError, ValueError):
        return None


def collect_relevant_geonames_records(
    source_dir: Path,
    entries: Iterable[PickerEntry],
) -> tuple[dict[str, list[GeoNamesRecord]], list[dict[str, str]]]:
    """Read the dumps once, retaining only target/province candidate records."""

    target_names_by_territory: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        target_names_by_territory[entry.territory].update(name_variants(entry.city))
        if entry.territory == "CN":
            target_names_by_territory[entry.territory].update(name_variants(entry.province))

    candidates_by_territory: dict[str, list[GeoNamesRecord]] = defaultdict(list)
    source_manifest: list[dict[str, str]] = []
    for country in SOURCE_COUNTRIES:
        text_path = source_dir / f"{country}.txt"
        archive_path = source_dir / f"{country}.zip"
        if not text_path.is_file() or not archive_path.is_file():
            raise FileNotFoundError(
                f"Expected both {text_path.name} and {archive_path.name} in {source_dir}"
            )
        source_manifest.append(
            {
                "territory": country,
                "download_url": f"https://download.geonames.org/export/dump/{country}.zip",
                "archive_sha256": sha256_file(archive_path),
                "extracted_file_sha256": sha256_file(text_path),
                "license": "CC BY 4.0",
            }
        )
        wanted_names = target_names_by_territory.get(country, set())
        if not wanted_names:
            continue
        with text_path.open("r", encoding="utf-8") as source:
            for line in source:
                row = line.rstrip("\n").rstrip("\r").split("\t")
                record = parse_geonames_row(row)
                if record is None or record.country_code != country:
                    continue
                if record.aliases.intersection(wanted_names):
                    candidates_by_territory[country].append(record)
    return candidates_by_territory, source_manifest


def find_province_admin1_code(
    province: str,
    records: Iterable[GeoNamesRecord],
) -> str:
    variants = name_variants(province)
    matches = [
        record
        for record in records
        if record.feature_code == "ADM1" and record.aliases.intersection(variants)
    ]
    codes = sorted({record.admin1_code for record in matches if record.admin1_code})
    if not codes:
        raise ValueError(f"No GeoNames ADM1 record for province {province}")
    if len(codes) != 1:
        raise ValueError(f"Ambiguous GeoNames ADM1 records for province {province}: {codes}")
    return codes[0]


def select_geonames_record(
    entry: PickerEntry,
    records: Iterable[GeoNamesRecord],
    province_admin1_codes: dict[str, str],
) -> GeoNamesRecord:
    variants = name_variants(entry.city)
    exact_name = normalize_name(entry.city)
    eligible: list[GeoNamesRecord] = []
    for record in records:
        if record.country_code != entry.territory or not record.aliases.intersection(variants):
            continue
        if entry.territory == "CN" and record.admin1_code != province_admin1_codes[entry.province]:
            continue
        eligible.append(record)
    if not eligible:
        raise ValueError(f"No GeoNames record for {entry.province}/{entry.city}")

    def rank(record: GeoNamesRecord) -> tuple[int, int, int]:
        exact = 0 if exact_name in record.aliases else 1
        return (exact, FEATURE_PRIORITY[record.feature_code], -record.population)

    eligible.sort(key=lambda record: (*rank(record), record.geoname_id))
    best = eligible[0]
    best_rank = rank(best)
    equally_ranked = [record for record in eligible if rank(record) == best_rank]
    if len(equally_ranked) != 1:
        choices = ", ".join(
            f"{record.geoname_id}:{record.name}/{record.feature_code}" for record in equally_ranked
        )
        raise ValueError(
            f"Ambiguous GeoNames record for {entry.province}/{entry.city}: {choices}"
        )
    return best


def picker_aliases(entry: PickerEntry) -> list[str]:
    aliases = [entry.city, f"{entry.province}{entry.city}"]
    for variant in sorted(name_variants(entry.city)):
        if variant not in aliases:
            aliases.append(variant)
    return aliases


def make_manual_record(entry: PickerEntry) -> dict[str, Any]:
    override = MANUAL_WIKIDATA_OVERRIDES[(entry.province, entry.city)]
    wikidata_id = override["wikidata_id"]
    return {
        "code": f"cn:wikidata:{wikidata_id.lower()}",
        "province": entry.province,
        "city": entry.city,
        "display_name": entry.city,
        "aliases": picker_aliases(entry),
        "longitude": override["longitude"],
        "latitude": override["latitude"],
        "timezone": TIMEZONE_BY_TERRITORY[entry.territory],
        "territory": entry.territory,
        "precision": "city-seat",
        "coordinate_origin": "manual-wikidata-override",
        "source": {
            "provider": "Wikidata",
            "record_id": wikidata_id,
            "url": f"https://www.wikidata.org/wiki/{wikidata_id}",
            "license": "CC0 1.0",
            "property": "P625",
        },
    }


def make_geonames_record(entry: PickerEntry, source: GeoNamesRecord) -> dict[str, Any]:
    return {
        "code": f"cn:geonames:{source.geoname_id}",
        "province": entry.province,
        "city": entry.city,
        "display_name": entry.city,
        "aliases": picker_aliases(entry),
        "longitude": source.longitude,
        "latitude": source.latitude,
        "timezone": TIMEZONE_BY_TERRITORY[entry.territory],
        "territory": entry.territory,
        "precision": "city-seat",
        "coordinate_origin": "geonames",
        "source": {
            "provider": "GeoNames",
            "record_id": source.geoname_id,
            "feature_code": source.feature_code,
            "source_timezone": source.timezone,
            "modified_at": source.modified_at,
            "license": "CC BY 4.0",
            "url": f"https://www.geonames.org/{source.geoname_id}",
        },
    }


def validate_records(entries: list[PickerEntry], records: list[dict[str, Any]]) -> None:
    expected = {(entry.province, entry.city) for entry in entries}
    actual = {(record["province"], record["city"]) for record in records}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(f"Picker coverage mismatch; missing={missing!r} extra={extra!r}")
    if len(records) != len(entries):
        raise ValueError(f"Expected {len(entries)} records, generated {len(records)}")
    codes = [record["code"] for record in records]
    if len(codes) != len(set(codes)):
        raise ValueError("Location codes must be unique")
    for record in records:
        longitude = float(record["longitude"])
        latitude = float(record["latitude"])
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError(f"Invalid WGS84 coordinate for {record['province']}/{record['city']}")
        if record["precision"] != "city-seat":
            raise ValueError(f"Unexpected precision for {record['province']}/{record['city']}")
        if record["timezone"] != TIMEZONE_BY_TERRITORY[record["territory"]]:
            raise ValueError(f"Incorrect IANA timezone for {record['province']}/{record['city']}")


def canonical_records_hash(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_dataset(source_dir: Path, picker_path: Path) -> dict[str, Any]:
    entries = read_picker_entries(picker_path)
    candidates_by_territory, source_manifest = collect_relevant_geonames_records(source_dir, entries)
    province_admin1_codes: dict[str, str] = {}
    for province in sorted({entry.province for entry in entries if entry.territory == "CN"}):
        province_admin1_codes[province] = find_province_admin1_code(
            province, candidates_by_territory["CN"]
        )

    records: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for entry in entries:
        override_key = (entry.province, entry.city)
        if override_key in MANUAL_WIKIDATA_OVERRIDES:
            records.append(make_manual_record(entry))
            continue
        try:
            source = select_geonames_record(
                entry,
                candidates_by_territory[entry.territory],
                province_admin1_codes,
            )
        except ValueError as exc:
            unresolved.append(str(exc))
            continue
        records.append(make_geonames_record(entry, source))
    if unresolved:
        raise ValueError("\n".join(unresolved))

    validate_records(entries, records)
    records_hash = canonical_records_hash(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
        "coordinate_reference_system": "WGS84",
        "precision": "city-seat",
        "geographic_scope": "Current mini-program province/city picker only",
        "coverage": {
            "province_count": len({entry.province for entry in entries}),
            "picker_entry_count": len(entries),
            "record_count": len(records),
        },
        "attribution": {
            "text": "Contains data from GeoNames, licensed under CC BY 4.0. Manual overrides use Wikidata coordinate statements (CC0).",
            "geonames_url": "https://www.geonames.org/",
            "geonames_license_url": "https://creativecommons.org/licenses/by/4.0/",
            "wikidata_license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        },
        "source_manifest": source_manifest,
        "manual_override_policy": {
            "count": len(MANUAL_WIKIDATA_OVERRIDES),
            "reason": "Picker entries absent from the downloaded GeoNames snapshot; explicit Wikidata P625 records are manually reviewed.",
        },
        "records_sha256": records_hash,
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Directory containing CN/TW/HK/MO .txt and .zip GeoNames dumps.",
    )
    parser.add_argument(
        "--picker",
        type=Path,
        default=DEFAULT_PICKER,
        help=f"Mini-program picker source (default: {DEFAULT_PICKER}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Generated JSON output (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the generated dataset against --output without overwriting it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        dataset = build_dataset(args.source_dir, args.picker)
    except (OSError, ValueError) as exc:
        print(f"Location dataset build failed: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(dataset, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Location dataset check failed: {exc}", file=sys.stderr)
            return 1
        if current != rendered:
            print(
                "Location dataset check failed: output is stale; rerun the generator.",
                file=sys.stderr,
            )
            return 1
        print(
            f"Location dataset is current: {dataset['coverage']['record_count']} picker entries, "
            f"records_sha256={dataset['records_sha256']}"
        )
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {args.output}: {dataset['coverage']['record_count']} picker entries, "
        f"records_sha256={dataset['records_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
