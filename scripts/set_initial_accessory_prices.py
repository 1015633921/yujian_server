from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

import pymysql


RULE_VERSION = "20260723-accessory-market-v1"
EXPECTED_ACCESSORY_SKUS = 87
EXPECTED_CATEGORY_COUNTS = {
    "三角牌": 2,
    "切面珠": 6,
    "包珠隔片": 1,
    "单尖": 4,
    "双尖": 3,
    "方糖": 13,
    "无事牌": 9,
    "花托": 9,
    "连接扣": 1,
    "随形": 2,
    "隔片": 2,
    "隔珠": 35,
}
BACKUP_TABLE_RE = re.compile(r"^managed_accessory_price_backup_\d{8}_\d{6}$")
METAL_ID_PREFIX = "mat_accessory_metal_"

# Public references reviewed on 2026-07-23. They provide directional anchors
# for ordinary alloy findings and natural crystal accessories. Final prices are
# conservative curated-studio retail prices per piece, not batch appraisals.
MARKET_SOURCES = (
    "https://www.yiwugo.com/product/detail/972789020.html",
    "https://www.jd.com/jiage/614432eebc962da395ab.html",
    "https://www.jd.com/jiage/614445cf4c7b0b4b7ce7.html",
    "https://www.jd.com/jiage/6144f444bbca35777390.html",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def half_yuan(value: Decimal | float | int | str) -> Decimal:
    amount = Decimal(str(value))
    return ((amount * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2).quantize(
        Decimal("0.00")
    )


def price_cents(price: Decimal) -> int:
    return int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _size(row: dict[str, Any]) -> Decimal:
    try:
        value = Decimal(str(row.get("size") or 0))
    except Exception as exc:
        raise ValueError(f"无效配饰尺寸: {row.get('size')!r}") from exc
    return max(value, Decimal("0"))


def metal_price(row: dict[str, Any]) -> Decimal:
    category = str(row.get("category") or "").strip()
    name = str(row.get("name") or row.get("series") or "").strip()
    size = _size(row)

    if category == "包珠隔片":
        return Decimal("5.50")
    if category == "连接扣":
        return Decimal("8.00")
    if category == "隔片":
        return Decimal("3.50") if size >= 7.5 else Decimal("3.00")
    if category == "花托":
        base = Decimal("3.00")
        if any(keyword in name for keyword in ("叶纹", "蝶纹")):
            base += Decimal("1.00")
        if any(keyword in name for keyword in ("繁花", "莲花", "莲蓬")):
            base += Decimal("1.50")
        if size >= 12:
            base += Decimal("1.50")
        return half_yuan(base)
    if category != "隔珠":
        raise ValueError(f"未覆盖的合金配饰分类: {category}")

    if size <= 3:
        base = Decimal("2.00")
    elif size <= 4.5:
        base = Decimal("2.50")
    elif size <= 6:
        base = Decimal("3.50")
    elif size <= 8:
        base = Decimal("4.50")
    elif size <= 10:
        base = Decimal("5.50")
    elif size <= 12:
        base = Decimal("6.50")
    else:
        base = Decimal("7.50")

    if any(keyword in name for keyword in ("方珠", "方形", "八卦", "八吉祥")):
        base += Decimal("1.00")
    if any(
        keyword in name
        for keyword in ("繁花", "玫瑰", "雪花", "蝴蝶结", "宫廷", "镂空", "羽毛", "花瓣")
    ):
        base += Decimal("1.50")
    elif any(keyword in name for keyword in ("卷云", "回纹", "麻花", "瓜棱", "四叶", "四瓣")):
        base += Decimal("0.50")
    if "锆石" in name:
        base += Decimal("5.00")
    return half_yuan(base)


def crystal_price(row: dict[str, Any]) -> Decimal:
    category = str(row.get("category") or "").strip()
    name = str(row.get("name") or row.get("series") or "").strip()
    size = _size(row)
    ghost_premium = Decimal("4.00") if "幽灵" in name else Decimal("0")

    if category == "方糖":
        value = Decimal("7.00") + size * Decimal("1.60") + ghost_premium
        if "白水" in name:
            value -= Decimal("5.00")
    elif category == "切面珠":
        value = Decimal("5.00") + size * Decimal("1.35") + ghost_premium
    elif category == "无事牌":
        value = Decimal("4.00") + size * Decimal("1.75") + ghost_premium
    elif category == "单尖":
        value = Decimal("5.00") + size * Decimal("1.80") + ghost_premium
    elif category == "双尖":
        value = Decimal("8.00") + size * Decimal("2.00") + ghost_premium
    elif category == "三角牌":
        value = Decimal("7.00") + size * Decimal("2.60") + ghost_premium
        if "白水" in name:
            value -= Decimal("16.00")
    elif category == "随形":
        value = Decimal("4.00") + size * Decimal("0.90")
    else:
        raise ValueError(f"未覆盖的水晶配饰分类: {category}")
    return max(Decimal("8.00"), half_yuan(value))


def price_for_accessory(row: dict[str, Any]) -> Decimal:
    item_id = str(row.get("id") or "")
    return metal_price(row) if item_id.startswith(METAL_ID_PREFIX) else crystal_price(row)


def connect_mysql():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
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


def validate_environment(*, allow_production: bool) -> None:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    database = os.getenv("MYSQL_DATABASE", "").strip().lower()
    is_production = app_env in {"production", "prod"} and not any(
        token in database for token in ("test", "dev", "local")
    )
    if is_production and allow_production:
        return
    if app_env in {"test", "testing", "staging"} and "test" in database:
        return
    raise SystemExit(
        f"拒绝当前环境调价: APP_ENV={app_env or '<empty>'} "
        f"MYSQL_DATABASE={database or '<empty>'}"
    )


def fetch_accessories(cursor, *, lock: bool = False) -> list[dict[str, Any]]:
    suffix = " FOR UPDATE" if lock else ""
    cursor.execute(
        """
        SELECT id, skuId, category, series, material_code, grade, name, size,
               price, price_cents, stock, enabled, updated_at
        FROM managed_materials
        WHERE top='accessory'
        ORDER BY category, series, size, id
        """ + suffix
    )
    return list(cursor.fetchall())


def validate_inventory(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    clean_rows = list(rows)
    if len(clean_rows) != EXPECTED_ACCESSORY_SKUS:
        raise ValueError(
            f"配饰 SKU 数应为 {EXPECTED_ACCESSORY_SKUS}，实际为 {len(clean_rows)}"
        )
    counts = Counter(str(row.get("category") or "").strip() for row in clean_rows)
    if dict(counts) != EXPECTED_CATEGORY_COUNTS:
        raise ValueError(
            f"配饰分类清单不一致: expected={EXPECTED_CATEGORY_COUNTS}, actual={dict(counts)}"
        )
    ids = [str(row.get("id") or "") for row in clean_rows]
    if any(not item_id for item_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("配饰存在空 id 或重复 id")
    return clean_rows


def build_pricing_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in validate_inventory(rows):
        new_price = price_for_accessory(row)
        result.append(
            {
                **row,
                "old_price": Decimal(str(row["price"])).quantize(Decimal("0.00")),
                "new_price": new_price,
                "new_price_cents": price_cents(new_price),
                "pricing_family": (
                    "metal" if str(row["id"]).startswith(METAL_ID_PREFIX) else "crystal"
                ),
            }
        )
    return result


def pricing_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [row["new_price"] for row in rows]
    return {
        "rule_version": RULE_VERSION,
        "scope": "all accessory SKUs",
        "sku_count": len(rows),
        "enabled_count": sum(bool(row["enabled"]) for row in rows),
        "changed_count": sum(
            row["old_price"] != row["new_price"]
            or int(row.get("price_cents") or 0) != row["new_price_cents"]
            for row in rows
        ),
        "metal_count": sum(row["pricing_family"] == "metal" for row in rows),
        "crystal_count": sum(row["pricing_family"] == "crystal" for row in rows),
        "min_price": f"{min(prices):.2f}",
        "max_price": f"{max(prices):.2f}",
        "by_category": {
            category: {
                "count": len(category_rows),
                "min": f"{min(row['new_price'] for row in category_rows):.2f}",
                "max": f"{max(row['new_price'] for row in category_rows):.2f}",
            }
            for category in EXPECTED_CATEGORY_COUNTS
            if (category_rows := [row for row in rows if row["category"] == category])
        },
    }


def backup_table_name() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"managed_accessory_price_backup_{stamp}"


def apply_prices(connection, rows: list[dict[str, Any]]) -> str:
    table = backup_table_name()
    if not BACKUP_TABLE_RE.fullmatch(table):
        raise ValueError("备份表名不安全")
    timestamp = now_iso()
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE TABLE `{table}` AS
            SELECT id, price, price_cents, updated_at
            FROM managed_materials
            WHERE top='accessory'
            """
        )
        cursor.execute(f"ALTER TABLE `{table}` ADD PRIMARY KEY (id)")
        cursor.executemany(
            """
            UPDATE managed_materials
            SET price=%s, price_cents=%s, updated_at=%s
            WHERE id=%s AND top='accessory'
            """,
            [
                (f"{row['new_price']:.2f}", row["new_price_cents"], timestamp, row["id"])
                for row in rows
            ],
        )
        cursor.execute(
            "SELECT id, price, price_cents FROM managed_materials WHERE top='accessory'"
        )
        actual = {
            str(row["id"]): (
                Decimal(str(row["price"])).quantize(Decimal("0.00")),
                int(row["price_cents"] or 0),
            )
            for row in cursor.fetchall()
        }
        expected = {
            str(row["id"]): (row["new_price"], row["new_price_cents"]) for row in rows
        }
        if actual != expected:
            mismatches = sorted(
                item_id
                for item_id in set(actual) | set(expected)
                if actual.get(item_id) != expected.get(item_id)
            )
            raise RuntimeError(f"价格写入核对失败: {mismatches[:10]}")

        cursor.execute("SHOW TABLES LIKE 'material_audit_logs'")
        if cursor.fetchone():
            summary = pricing_summary(rows)
            cursor.execute(
                """
                INSERT INTO material_audit_logs
                (log_id, action, target_type, target_id, material_id, material_code,
                 actor_id, actor_name, summary, before_json, after_json, created_at)
                VALUES (%s, %s, %s, %s, '', '', %s, %s, %s, %s, %s, %s)
                """,
                (
                    f"matlog_{secrets.token_hex(12)}",
                    "batch_initial_accessory_price",
                    "material_price_batch",
                    table,
                    "codex-production-migration",
                    "Codex",
                    f"按 {RULE_VERSION} 设置 {len(rows)} 个配饰 SKU 初始价",
                    json.dumps({"backup_table": table}, ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False),
                    timestamp,
                ),
            )
    return table


def rollback_prices(connection, table: str) -> int:
    if not BACKUP_TABLE_RE.fullmatch(table):
        raise ValueError("仅允许使用本脚本生成的配饰价格备份表")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM information_schema.tables "
            "WHERE table_schema=DATABASE() AND table_name=%s",
            (table,),
        )
        if int(cursor.fetchone()["total"]) != 1:
            raise ValueError(f"备份表不存在: {table}")
        cursor.execute(f"SELECT COUNT(*) AS total FROM `{table}`")
        total = int(cursor.fetchone()["total"])
        if total != EXPECTED_ACCESSORY_SKUS:
            raise ValueError(
                f"备份行数异常: expected={EXPECTED_ACCESSORY_SKUS}, actual={total}"
            )
        cursor.execute(
            f"""
            UPDATE managed_materials AS m
            JOIN `{table}` AS b ON b.id=m.id
            SET m.price=b.price, m.price_cents=b.price_cents, m.updated_at=b.updated_at
            WHERE m.top='accessory'
            """
        )
        cursor.execute(
            f"""
            SELECT COUNT(*) AS mismatches
            FROM managed_materials AS m
            JOIN `{table}` AS b ON b.id=m.id
            WHERE m.price<>b.price
               OR COALESCE(m.price_cents, -1)<>COALESCE(b.price_cents, -1)
               OR COALESCE(m.updated_at, '')<>COALESCE(b.updated_at, '')
            """
        )
        if int(cursor.fetchone()["mismatches"]) != 0:
            raise ValueError("回滚后价格与备份不一致")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Set initial per-piece accessory prices")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--rollback-table")
    args = parser.parse_args()
    if args.apply and args.rollback_table:
        parser.error("--apply 与 --rollback-table 不能同时使用")
    validate_environment(allow_production=args.allow_production)
    connection = connect_mysql()
    try:
        if args.rollback_table:
            restored = rollback_prices(connection, args.rollback_table)
            connection.commit()
            print(
                json.dumps(
                    {"restored": restored, "backup_table": args.rollback_table},
                    ensure_ascii=False,
                )
            )
            return
        with connection.cursor() as cursor:
            rows = build_pricing_rows(fetch_accessories(cursor, lock=args.apply))
        payload: dict[str, Any] = {"summary": pricing_summary(rows)}
        if args.apply:
            payload["backup_table"] = apply_prices(connection, rows)
            connection.commit()
        else:
            connection.rollback()
        payload["preview"] = [
            {
                "id": row["id"],
                "category": row["category"],
                "name": row["name"],
                "size": float(row["size"] or 0),
                "old_price": f"{row['old_price']:.2f}",
                "new_price": f"{row['new_price']:.2f}",
            }
            for row in rows
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
