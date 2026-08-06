from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymysql

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fortune.crystal_taxonomy import taxonomy_for
from app.material_options import (
    CARE_TAG_OPTIONS,
    COLOR_FAMILY_OPTIONS,
    EFFECT_OPTIONS,
    ELEMENT_OPTIONS,
    MATCH_RULE_OPTIONS,
    MOOD_TAG_OPTIONS,
    ROLE_OPTIONS,
    VISUAL_TAG_OPTIONS,
    WISH_POOL_OPTIONS,
)


RULE_VERSION = "20260723-production-bead-knowledge-v1"
EXPECTED_ACTIVE_BEAD_SKUS = 231
BACKUP_TABLE_RE = re.compile(r"^material_knowledge_bead_backup_\d{8}_\d{6}$")

# Mineral appearance and care wording was checked against GIA/Gem-A material.
# Five-element and wish tags are product design metadata only; the public story
# deliberately describes them as traditional-culture and styling references.
REFERENCE_SOURCES = (
    "https://www.gia.edu/amethyst",
    "https://www.gia.edu/ametrine-care-cleaning",
    "https://www.gia.edu/gem-treatment",
    "https://www.gia.edu/gems-gemology/summer-2025-phenomenal-gemstones",
    "https://gem-a.com/wp-content/uploads/2023/09/CIBJO-The-Gemstone-Book.pdf",
)

PROFILE_SPECS: dict[str, dict[str, Any]] = {
    "mat_191b0a213004cbad": {
        "base": "amethyst",
        "name": "乌拉圭紫晶",
        "rules": ["best_as_primary", "needs_color_balance"],
        "story": "深紫至红紫色调集中，通透处会呈现清晰的明暗层次。适合做主石，搭配白水晶、银色隔珠或少量浅紫珠；避免同时堆叠多种高饱和色。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "rose_quartz": {
        "base": "rose_quartz",
        "name": "粉水晶",
        "story": "粉水晶以柔和粉色、半透明至微透质地为主要特征，不同品种可见星光、冰润或暖橘粉调。适合与白水晶、紫晶、月光色珠材及银色配饰组合；大面积使用时用清透珠提亮。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "mat_a73522dec5274817": {
        "base": "clear_quartz",
        "name": "双A白水",
        "story": "整体清透、明亮，适合作为主石或连接不同色系的过渡珠。可与几乎所有珠材搭配，尤其适合银色隔珠、紫晶、粉晶和幽灵类；作为辅石时能减少综合色的拥挤感。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "four_seasons_phantom": {
        "base": "colorful_phantom",
        "name": "四季幽灵",
        "rules": ["best_as_primary", "needs_color_balance"],
        "story": "晶体内常见绿、红、黄或灰白色矿物景观，单颗之间纹理差异明显。适合做主石，搭配白水晶、茶晶或简洁金银配饰；内含色较丰富时减少其他花色珠比例。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "mat_41f9a6e4d6fd8150": {
        "base": "amethyst",
        "name": "巴西紫晶",
        "rules": ["no_limit", "needs_color_balance"],
        "story": "紫色由浅至深、整体清透感较强，适合日常通勤和低饱和配色。可搭配白水晶、粉晶、薰衣草紫晶及银色配饰；深紫珠较多时加入透明珠留出呼吸感。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "mat_02ed66d41de6605c": {
        "base": "gold_rutilated_quartz",
        "name": "彩发晶",
        "elements": ["metal", "fire", "wood"],
        "effects": ["career", "focus", "inspiration"],
        "wishes": ["career", "focus", "inspiration"],
        "color": "gold",
        "moods": ["confidence", "focus", "vitality"],
        "visual": ["transparent", "texture", "sparkling"],
        "roles": ["primary", "support", "accent"],
        "rules": ["best_as_primary", "needs_color_balance"],
        "story": "透明晶体中可见多色发丝或针状包体，纹理方向和密度是主要观赏点。适合做主石，搭配白水晶、茶晶或简洁金银配饰；发丝色较杂时避免再叠加过多花色珠。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "quartz_inclusion": {
        "base": "quartz_inclusion",
        "name": "闪灵胶花水晶",
        "roles": ["primary", "support", "accent"],
        "rules": ["needs_color_balance"],
        "story": "以晶体内胶花、闪片、絮状或矿物包体形成独特景观，同批珠子的纹理差异通常较大。适合搭配白水晶、茶晶和简洁金属隔珠；花色越复杂，其他珠材越应保持单色。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "labradorite": {
        "base": "labradorite",
        "name": "拉长石",
        "story": "灰蓝底色在转动时可出现蓝、绿或金色晕彩，光线角度会明显影响观感。建议少量作主石或点缀，搭配白水晶、月光色珠材、黑色珠材及银色配饰；避免与多种强闪光珠密集混用。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "kyanite": {
        "base": "kyanite",
        "name": "蓝晶石",
        "roles": ["primary", "support", "accent"],
        "rules": ["best_as_support", "needs_color_balance"],
        "story": "蓝晶石常呈深浅蓝色、条带或猫眼光感，不同品种可偏油画纹理或玉化质感。适合搭配白水晶、银色隔珠、海蓝色或黑色珠材；深蓝占比高时加入清透珠平衡。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "mat_bd18a0d596f6fd30": {
        "base": "amethyst",
        "name": "玻利维亚紫水晶",
        "rules": ["best_as_primary", "needs_color_balance"],
        "story": "紫色清晰，部分珠体可出现深浅色带或暖色过渡，适合成为整串视觉中心。可搭配白水晶、紫黄晶、银色或少量金色配饰；综合色明显时减少其他彩色主石。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "clear_quartz": {
        "base": "clear_quartz",
        "name": "白水晶",
        "story": "白水晶以无色清透、冰裂或轻微云雾感为主要视觉特征，是适配范围很广的基础珠材。可用于主石、辅石或色彩过渡，搭配任意彩色水晶和金银配饰；净体与内含物属于不同审美方向。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "mat_6c993e4cebe41a41": {
        "base": "clear_quartz",
        "name": "白阿塞",
        "color": "white",
        "visual": ["transparent", "icy", "milky"],
        "story": "“白阿塞”是市场常用名称，视觉上以白色、清透或云雾内含为主，天然纹理会有批次差异。适合搭配银色配饰、幽灵类、紫晶和粉晶，也可作为综合色之间的留白珠。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "mat_9ec8c56283c46796": {
        "base": "ametrine",
        "name": "紫黄晶",
        "rules": ["best_as_primary", "needs_color_balance"],
        "story": "同一晶体中可见紫色与黄色分区或渐变，冷暖对比是其主要特点。适合做主石，搭配白水晶、浅紫珠以及少量金银配饰；避免与过多红绿撞色同时密集使用。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "rabbit_hair_quartz": {
        "base": "rabbit_hair_quartz",
        "name": "兔毛水晶",
        "roles": ["primary", "support", "accent"],
        "rules": ["best_as_primary", "needs_color_balance", "avoid_dense"],
        "story": "晶体中细密发丝或絮状包体呈红、绿、黄等色，纹理密度和方向让每颗珠子都不同。适合做主石或少量点缀，搭配白水晶、同色纯色珠及简洁金银配饰；避免多种兔毛高密度混排。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "red_phantom": {
        "base": "red_phantom",
        "name": "红幽灵",
        "rules": ["best_as_primary", "needs_color_balance"],
        "story": "透明晶体内可见红褐色矿物层、聚宝盆或云雾景观，单珠画面感较强。适合做主石，搭配白水晶、茶晶、金色或古金色小配饰；高密度红色内含应与清透珠交替。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "c58e5e42bc727230": {
        "base": "red_rutilated_quartz",
        "name": "红铜发",
        "rules": ["best_as_primary", "needs_color_balance", "avoid_dense"],
        "story": "透明至半透明晶体中可见铜红、红棕色针状或发丝状包体，整体偏暖且存在感强。适合做主石，搭配白水晶、茶晶和少量金色配饰；避免与多种暖红珠高密度堆叠。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "green_rutilated_quartz": {
        "base": "green_rutilated_quartz",
        "name": "绿发晶",
        "roles": ["primary", "support", "accent"],
        "rules": ["best_as_support", "needs_color_balance"],
        "story": "晶体中绿色针丝或束状内含形成线性纹理，颜色可从浅绿到深绿变化。适合搭配白水晶、绿幽灵、茶晶及银色配饰；发丝密集时以清透珠降低视觉重量。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "green_phantom": {
        "base": "green_phantom",
        "name": "绿幽灵",
        "rules": ["best_as_primary", "needs_color_balance"],
        "story": "透明晶体内的绿色矿物形成层叠、山景、满天星或聚宝盆形态，天然景观差异明显。适合做主石，搭配白水晶、茶晶及简洁金银配饰；景观珠比例较高时减少其他复杂内含物。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "mat_e6cb260f0670a194": {
        "base": "amethyst",
        "name": "薰衣草紫晶",
        "color": "purple",
        "moods": ["softness", "calming", "clarity"],
        "rules": ["best_as_support", "no_limit"],
        "story": "低饱和浅紫色调柔和，整体比深紫晶更轻盈，适合日常和夏季配色。可搭配白水晶、粉晶、月光色珠材及银色配饰，也适合作为深紫主石的过渡珠。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "gold_rutilated_quartz": {
        "base": "gold_rutilated_quartz",
        "name": "金发晶",
        "rules": ["best_as_primary", "needs_color_balance", "avoid_dense"],
        "story": "透明晶体中金色针丝、束发或板钛形成强烈光泽和方向感，发丝密度决定视觉重量。适合做主石，搭配白水晶、茶晶和少量金色配饰；避免与多种金色高光材料密集叠加。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "titanium_quartz": {
        "base": "titanium_quartz",
        "name": "钛晶",
        "rules": ["best_as_primary", "needs_color_balance", "avoid_dense"],
        "story": "晶体内金色板状、束状或粗针状包体反光强，通常适合作为整串焦点。建议搭配白水晶、茶晶、黑色珠材或少量金色配饰；一至三颗重点使用比整串堆叠更显层次。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "mat_4ffa5cb3f1f4c2a1": {
        "base": "silver_rutilated_quartz",
        "name": "银发晶",
        "color": "white",
        "rules": ["best_as_support", "needs_color_balance"],
        "story": "透明晶体中的银灰、白色针丝带来冷调线性光泽，整体比金色发晶更克制。适合搭配白水晶、黑发晶、蓝色珠材及银色配饰；发丝密集时加入净体珠留白。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "mat_c70ba9a2e0cef45b": {
        "base": "blue_tiger_eye",
        "name": "鹰眼石",
        "roles": ["primary", "support", "accent"],
        "rules": ["best_as_support", "needs_color_balance"],
        "story": "深蓝至蓝灰底色上可见移动的猫眼光带，转动时明暗变化明显。适合搭配白水晶、黑色珠材、蓝晶石和银色配饰；深色占比过高时用清透珠或浅色隔珠提亮。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
    "black_rutilated_quartz": {
        "base": "black_rutilated_quartz",
        "name": "黑发晶",
        "rules": ["best_as_support", "needs_color_balance", "avoid_dense"],
        "story": "透明至烟灰晶体中黑色针丝交错，线条感强，整体冷峻且对比鲜明。适合搭配白水晶、银发晶、鹰眼石和银色配饰；黑色发丝密集时避免整串全部使用深色珠。五行与愿景标签仅作传统文化和设计灵感参考。",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def option_keys(options: tuple[dict[str, str], ...]) -> set[str]:
    return {item["key"] for item in options}


VALID_OPTIONS = {
    "elements": option_keys(ELEMENT_OPTIONS),
    "effects": option_keys(EFFECT_OPTIONS),
    "wishes": option_keys(WISH_POOL_OPTIONS),
    "colors": option_keys(COLOR_FAMILY_OPTIONS),
    "moods": option_keys(MOOD_TAG_OPTIONS),
    "visual": option_keys(VISUAL_TAG_OPTIONS),
    "roles": option_keys(ROLE_OPTIONS),
    "rules": option_keys(MATCH_RULE_OPTIONS),
    "care": option_keys(CARE_TAG_OPTIONS),
}


def valid_list(values: Any, key: str) -> list[str]:
    allowed = VALID_OPTIONS[key]
    return [str(value) for value in values or [] if str(value) in allowed]


def build_profile(code: str, spec: dict[str, Any]) -> dict[str, Any]:
    taxonomy = taxonomy_for(spec["base"])
    elements = valid_list(spec.get("elements", taxonomy.get("elements")), "elements")
    effects = valid_list(spec.get("effects", taxonomy.get("effects")), "effects")
    wishes = valid_list(spec.get("wishes", taxonomy.get("wish_tags")), "wishes")
    colors = valid_list(taxonomy.get("color_families"), "colors")
    moods = valid_list(spec.get("moods", taxonomy.get("mood_tags")), "moods")
    visual = valid_list(spec.get("visual", taxonomy.get("visual_tags")), "visual")
    roles = valid_list(spec.get("roles", taxonomy.get("allowed_roles")), "roles")
    rules = valid_list(spec.get("rules", taxonomy.get("match_rules")), "rules")
    care = valid_list(spec.get("care", taxonomy.get("care_tags")), "care")
    color = str(spec.get("color") or (colors[0] if colors else ""))
    if color not in VALID_OPTIONS["colors"]:
        raise ValueError(f"{code}: invalid color family {color!r}")
    if not elements or not effects or not wishes or not moods or not visual or not roles or not rules or not care:
        raise ValueError(f"{code}: incomplete profile after normalization")
    return {
        "code": code,
        "name": spec["name"],
        "primary_element": elements[0],
        "secondary_elements": elements[1:],
        "chakras": list(dict.fromkeys(taxonomy.get("chakras") or [])),
        "effects": effects,
        "wish_pools": wishes,
        "color_family": color,
        "mood_tags": moods,
        "visual_tags": visual,
        "story": spec["story"],
        "allowed_roles": roles,
        "conflict_codes": [],
        "match_rules": rules,
        "care_tags": care,
        "material_params": taxonomy.get("material_params") or {},
    }


def build_profiles() -> dict[str, dict[str, Any]]:
    profiles = {code: build_profile(code, spec) for code, spec in PROFILE_SPECS.items()}
    if len(profiles) != 24:
        raise ValueError(f"expected 24 bead knowledge profiles, got {len(profiles)}")
    return profiles


def connect_mysql():
    return pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=20,
        read_timeout=60,
        write_timeout=60,
    )


def validate_environment(allow_production: bool) -> None:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    database = os.getenv("MYSQL_DATABASE", "").strip().lower()
    if not allow_production or app_env not in {"prod", "production"}:
        raise SystemExit("production update requires APP_ENV=production and --allow-production")
    if not database or any(marker in database for marker in ("test", "local", "dev")):
        raise SystemExit(f"refusing non-production database: {database or '<empty>'}")


def fetch_active_codes(cursor, *, lock: bool = False) -> tuple[int, set[str]]:
    suffix = " FOR UPDATE" if lock else ""
    cursor.execute(
        """
        SELECT material_code
        FROM managed_materials
        WHERE top='bead' AND enabled=1
        """ + suffix
    )
    rows = cursor.fetchall()
    return len(rows), {str(row["material_code"]) for row in rows}


def create_backup(cursor, table_name: str, codes: list[str]) -> int:
    if not BACKUP_TABLE_RE.fullmatch(table_name):
        raise ValueError(f"invalid backup table name: {table_name}")
    cursor.execute(f"CREATE TABLE `{table_name}` LIKE material_knowledge")
    placeholders = ", ".join(["%s"] * len(codes))
    cursor.execute(
        f"INSERT INTO `{table_name}` SELECT * FROM material_knowledge WHERE code IN ({placeholders})",
        codes,
    )
    cursor.execute(f"SELECT COUNT(*) AS count FROM `{table_name}`")
    return int(cursor.fetchone()["count"])


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def upsert_profile(cursor, profile: dict[str, Any], timestamp: str) -> None:
    cursor.execute("SELECT * FROM material_knowledge WHERE code=%s FOR UPDATE", (profile["code"],))
    existing = cursor.fetchone()
    material_params = (
        existing.get("material_params_json")
        if existing and existing.get("material_params_json") not in (None, "")
        else json_text(profile["material_params"])
    )
    asset = (
        existing.get("asset_json")
        if existing and existing.get("asset_json") not in (None, "")
        else "{}"
    )
    chakra_weights = (
        existing.get("chakra_weights_json")
        if existing and existing.get("chakra_weights_json") not in (None, "")
        else "{}"
    )
    values = (
        profile["name"],
        profile["primary_element"],
        json_text(profile["secondary_elements"]),
        json_text(profile["chakras"]),
        chakra_weights,
        json_text(profile["effects"]),
        json_text(profile["wish_pools"]),
        profile["color_family"],
        json_text(profile["mood_tags"]),
        json_text(profile["visual_tags"]),
        profile["story"],
        json_text(profile["allowed_roles"]),
        json_text(profile["conflict_codes"]),
        json_text(profile["match_rules"]),
        json_text(profile["care_tags"]),
        material_params,
        asset,
        1,
        timestamp,
    )
    if existing:
        cursor.execute(
            """
            UPDATE material_knowledge SET
              name=%s, primary_element=%s, secondary_elements_json=%s, chakras_json=%s,
              chakra_weights_json=%s, effects_json=%s, wish_pools_json=%s, color_family=%s,
              mood_tags_json=%s, visual_tags_json=%s, story=%s, allowed_roles_json=%s,
              conflict_codes_json=%s, match_rules_json=%s, care_tags_json=%s,
              material_params_json=%s, asset_json=%s, enabled=%s, updated_at=%s
            WHERE code=%s
            """,
            (*values, profile["code"]),
        )
    else:
        cursor.execute(
            """
            INSERT INTO material_knowledge (
              code, name, primary_element, secondary_elements_json, chakras_json,
              chakra_weights_json, effects_json, wish_pools_json, color_family,
              mood_tags_json, visual_tags_json, story, allowed_roles_json,
              conflict_codes_json, match_rules_json, care_tags_json,
              material_params_json, asset_json, enabled, created_at, updated_at
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s
            )
            """,
            (
                profile["code"],
                *values[:-1],
                timestamp,
                timestamp,
            ),
        )


def validate_rows(cursor, codes: list[str]) -> dict[str, Any]:
    placeholders = ", ".join(["%s"] * len(codes))
    cursor.execute(
        f"""
        SELECT *
        FROM material_knowledge
        WHERE enabled=1 AND code IN ({placeholders})
        ORDER BY code
        """,
        codes,
    )
    rows = cursor.fetchall()
    if len(rows) != len(codes):
        found = {row["code"] for row in rows}
        raise ValueError(f"active knowledge coverage mismatch, missing={sorted(set(codes) - found)}")
    for row in rows:
        for column in (
            "primary_element",
            "effects_json",
            "wish_pools_json",
            "color_family",
            "mood_tags_json",
            "visual_tags_json",
            "story",
            "allowed_roles_json",
            "match_rules_json",
            "care_tags_json",
        ):
            if row.get(column) in (None, "", "[]", "null"):
                raise ValueError(f"{row['code']}: incomplete {column}")
        if "传统文化和设计灵感参考" not in row["story"]:
            raise ValueError(f"{row['code']}: story disclaimer missing")
    cursor.execute(
        f"""
        SELECT COUNT(*) AS sku_count, COUNT(DISTINCT m.material_code) AS code_count
        FROM managed_materials m
        JOIN material_knowledge k ON k.code=m.material_code AND k.enabled=1
        WHERE m.top='bead' AND m.enabled=1 AND m.material_code IN ({placeholders})
        """,
        codes,
    )
    return dict(cursor.fetchone())


def rollback_sql(table_name: str, codes: list[str]) -> str:
    quoted_codes = ", ".join("'" + code.replace("'", "''") + "'" for code in codes)
    return (
        "START TRANSACTION; "
        f"DELETE FROM material_knowledge WHERE code IN ({quoted_codes}); "
        f"INSERT INTO material_knowledge SELECT * FROM `{table_name}`; "
        "COMMIT;"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich all active production bead knowledge records")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()
    validate_environment(args.allow_production)
    profiles = build_profiles()
    codes = sorted(profiles)
    timestamp = now_iso()
    backup_table = "material_knowledge_bead_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    connection = connect_mysql()
    try:
        with connection.cursor() as cursor:
            sku_count, active_codes = fetch_active_codes(cursor)
            if sku_count != EXPECTED_ACTIVE_BEAD_SKUS:
                raise ValueError(f"active bead SKU count changed: expected {EXPECTED_ACTIVE_BEAD_SKUS}, got {sku_count}")
            if active_codes != set(codes):
                raise ValueError(
                    f"active bead knowledge code set changed: "
                    f"missing_profiles={sorted(active_codes - set(codes))}, "
                    f"unused_profiles={sorted(set(codes) - active_codes)}"
                )
            print(json.dumps({
                "rule_version": RULE_VERSION,
                "mode": "apply" if args.apply else "dry-run",
                "active_bead_skus": sku_count,
                "knowledge_codes": len(codes),
                "sources": list(REFERENCE_SOURCES),
            }, ensure_ascii=False))
            if not args.apply:
                return

            backup_count = create_backup(cursor, backup_table, codes)
            connection.commit()
            cursor.execute("START TRANSACTION")
            locked_count, locked_codes = fetch_active_codes(cursor, lock=True)
            if locked_count != sku_count or locked_codes != active_codes:
                raise ValueError("active bead catalog changed while preparing update")
            for code in codes:
                upsert_profile(cursor, profiles[code], timestamp)
            validation = validate_rows(cursor, codes)
            connection.commit()
            print(json.dumps({
                "status": "updated",
                "backup_table": backup_table,
                "backup_rows": backup_count,
                "validation": validation,
                "rollback_sql": rollback_sql(backup_table, codes),
            }, ensure_ascii=False))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
