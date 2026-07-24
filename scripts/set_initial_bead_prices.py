from __future__ import annotations

import argparse
import csv
import json
import os
import re
import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

import pymysql

try:
    from scripts.local_env import load_env_file
except ModuleNotFoundError:  # Direct execution: python scripts/set_initial_bead_prices.py
    from local_env import load_env_file


ROOT = Path(__file__).resolve().parent.parent
RULE_VERSION = "20260722-market-v2-premium-crystal"
EXPECTED_ACTIVE_SKUS = 312
REQUIRED_SIZES = tuple(range(8, 16))
BACKUP_TABLE_RE = re.compile(r"^managed_material_price_backup_\d{8}_\d{6}$")

# Public market anchors reviewed on 2026-07-22. Prices below are deliberately
# conservative initial retail anchors for one ordinary commercial-grade 8 mm
# round bead. They are not appraisals of an individual batch.
MARKET_SOURCES = (
    "https://yiwugo.com/product/detail/980219975.html",
    "https://www.yiwugo.com/product/detail/985479651.html",
    "https://www.yiwugo.com/product/detail/985484652.html",
    "https://www.yiwugo.com/product/detail/976675970.html",
    "https://www.yiwugo.com/product/detail/958877393.html",
)

SIZE_FACTORS_BY_CURVE: dict[str, dict[int, Decimal]] = {
    # Common stones: larger beads carry a moderate premium.
    "C": dict(zip(REQUIRED_SIZES, map(Decimal, ("1", "1.266", "1.562", "1.891", "2.250", "2.641", "3.062", "3.516")))),
    # Selected/inclusion stones: usable yield falls faster as diameter grows.
    "M": dict(zip(REQUIRED_SIZES, map(Decimal, ("1", "1.303", "1.652", "2.047", "2.490", "2.981", "3.522", "4.114")))),
    # Scarce rutilated stones: large clean rounds command the steepest premium.
    "R": dict(zip(REQUIRED_SIZES, map(Decimal, ("1", "1.342", "1.747", "2.217", "2.756", "3.366", "4.051", "4.814")))),
}

# Exact active series whitelist. Using series rather than material_code is
# intentional: several distinct varieties share the same material_code.
SERIES_PRICE_PROFILES: dict[str, tuple[str, Decimal]] = {
    # Premium families are positioned above ordinary commercial-grade quartz:
    # rabbit-hair/phantom anchors are ~28% higher and rutilated anchors ~25%.
    "猫眼彩兔毛": ("M", Decimal("11.5")),
    "红兔毛": ("M", Decimal("9.0")),
    "绿兔毛": ("M", Decimal("9.0")),
    "钢丝彩兔毛": ("M", Decimal("12.0")),
    "黄兔毛": ("M", Decimal("9.0")),
    "彩发晶": ("R", Decimal("11.5")),
    "红铜发": ("R", Decimal("11.5")),
    "绿发晶": ("R", Decimal("10.0")),
    "金发晶": ("R", Decimal("16.5")),
    "钛晶": ("R", Decimal("20.0")),
    "银发晶": ("R", Decimal("10.5")),
    "黑发晶": ("R", Decimal("8.0")),
    "四季幽灵": ("M", Decimal("9.0")),
    "四季幽灵半盆": ("M", Decimal("7.5")),
    "火烧云幽灵": ("M", Decimal("10.0")),
    "红幽灵": ("M", Decimal("8.0")),
    "红幽灵聚宝盆": ("M", Decimal("10.0")),
    "绿幽灵": ("M", Decimal("9.0")),
    "红玛瑙": ("C", Decimal("2.0")),
    "双A白水": ("C", Decimal("3.5")),
    "白水晶": ("C", Decimal("2.5")),
    "白阿塞": ("C", Decimal("4.0")),
    "六芒星光粉": ("M", Decimal("6.5")),
    "冰橘粉": ("C", Decimal("4.5")),
    "粉水晶马粉": ("C", Decimal("3.0")),
    "西柚粉水晶": ("C", Decimal("4.0")),
    "乌拉圭紫晶": ("M", Decimal("7.0")),
    "巴西紫晶": ("C", Decimal("4.0")),
    "玻利维亚紫水晶": ("M", Decimal("5.0")),
    "紫黄晶": ("M", Decimal("6.5")),
    "薰衣草紫晶": ("C", Decimal("4.5")),
    "闪灵胶花": ("M", Decimal("8.5")),
    "拉长石": ("C", Decimal("3.5")),
    "油画蓝晶石": ("M", Decimal("4.5")),
    "猫眼蓝晶石": ("M", Decimal("6.0")),
    "玉化蓝晶石": ("M", Decimal("5.0")),
    "彩闪灵": ("M", Decimal("5.5")),
    "黑闪灵": ("M", Decimal("5.0")),
    "鹰眼石": ("C", Decimal("3.0")),
}

SERIES_8MM_ANCHORS = {series: profile[1] for series, profile in SERIES_PRICE_PROFILES.items()}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def price_for_series_size(series: str, size_mm: int | float) -> Decimal:
    try:
        size = int(size_mm)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"无效珠径: {size_mm!r}") from exc
    if float(size_mm) != size or size not in REQUIRED_SIZES:
        raise ValueError(f"珠径必须是 8-15mm 整数，收到: {size_mm!r}")
    try:
        curve, anchor = SERIES_PRICE_PROFILES[series]
    except KeyError as exc:
        raise ValueError(f"品种没有定价锚点: {series}") from exc
    half_yuan_units = (anchor * SIZE_FACTORS_BY_CURVE[curve][size] * 2).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return (half_yuan_units / 2).quantize(Decimal("0.00"))


def price_cents(price: Decimal) -> int:
    return int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


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


def validate_test_environment() -> None:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    database = os.getenv("MYSQL_DATABASE", "").strip().lower()
    if app_env not in {"test", "testing", "staging"} or "test" not in database:
        raise SystemExit(
            f"拒绝非测试环境调价: APP_ENV={app_env or '<empty>'} "
            f"MYSQL_DATABASE={database or '<empty>'}"
        )


def fetch_active_beads(cursor, *, lock: bool = False) -> list[dict[str, Any]]:
    suffix = " FOR UPDATE" if lock else ""
    cursor.execute(
        """
        SELECT id, skuId, category, series, material_code, grade, name, size,
               price, price_cents, stock, enabled, updated_at
        FROM managed_materials
        WHERE top='bead' AND enabled=1
        ORDER BY category, series, size, id
        """ + suffix
    )
    return list(cursor.fetchall())


def validate_inventory(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    clean_rows = list(rows)
    if len(clean_rows) != EXPECTED_ACTIVE_SKUS:
        raise ValueError(f"启用珠子 SKU 数应为 {EXPECTED_ACTIVE_SKUS}，实际为 {len(clean_rows)}")

    found_series = {str(row.get("series") or "").strip() for row in clean_rows}
    expected_series = set(SERIES_8MM_ANCHORS)
    if found_series != expected_series:
        missing = sorted(expected_series - found_series)
        unexpected = sorted(found_series - expected_series)
        raise ValueError(f"启用品种白名单不一致: missing={missing}, unexpected={unexpected}")

    ids: set[str] = set()
    sizes_by_series: dict[str, set[int]] = {}
    for row in clean_rows:
        item_id = str(row["id"])
        if item_id in ids:
            raise ValueError(f"重复材料 id: {item_id}")
        ids.add(item_id)
        series = str(row["series"]).strip()
        size_value = float(row["size"])
        size = int(size_value)
        if size_value != size:
            raise ValueError(f"{series} 存在非整数珠径: {size_value}")
        sizes_by_series.setdefault(series, set()).add(size)

    required = set(REQUIRED_SIZES)
    invalid = {series: sorted(sizes) for series, sizes in sizes_by_series.items() if sizes != required}
    if invalid:
        raise ValueError(f"品种珠径不完整: {invalid}")
    return clean_rows


def build_pricing_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in validate_inventory(rows):
        series = str(row["series"]).strip()
        size = int(float(row["size"]))
        new_price = price_for_series_size(series, size)
        result.append(
            {
                **row,
                "size": size,
                "old_price": Decimal(str(row["price"])).quantize(Decimal("0.00")),
                "new_price": new_price,
                "new_price_cents": price_cents(new_price),
                "price_curve": SERIES_PRICE_PROFILES[series][0],
                "anchor_8mm": SERIES_PRICE_PROFILES[series][1],
            }
        )
    return result


def pricing_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_size: dict[str, dict[str, Any]] = {}
    for size in REQUIRED_SIZES:
        prices = [row["new_price"] for row in rows if row["size"] == size]
        by_size[str(size)] = {
            "min": f"{min(prices):.2f}",
            "max": f"{max(prices):.2f}",
        }
    return {
        "rule_version": RULE_VERSION,
        "scope": "enabled bead SKUs only",
        "sku_count": len(rows),
        "series_count": len({row["series"] for row in rows}),
        "changed_count": sum(
            row["old_price"] != row["new_price"] or int(row.get("price_cents") or 0) != row["new_price_cents"]
            for row in rows
        ),
        "price_range_by_size": by_size,
    }


def export_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "id",
                "skuId",
                "category",
                "series",
                "size_mm",
                "old_price",
                "new_price",
                "new_price_cents",
                "price_curve",
                "anchor_8mm",
                "rule_version",
            ),
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row["id"],
                    "skuId": row["skuId"],
                    "category": row["category"],
                    "series": row["series"],
                    "size_mm": row["size"],
                    "old_price": f"{row['old_price']:.2f}",
                    "new_price": f"{row['new_price']:.2f}",
                    "new_price_cents": row["new_price_cents"],
                    "price_curve": row["price_curve"],
                    "anchor_8mm": f"{row['anchor_8mm']:.2f}",
                    "rule_version": RULE_VERSION,
                }
            )


def backup_table_name() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"managed_material_price_backup_{stamp}"


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
            WHERE top='bead' AND enabled=1
            """
        )
        cursor.execute(f"ALTER TABLE `{table}` ADD PRIMARY KEY (id)")
        cursor.executemany(
            """
            UPDATE managed_materials
            SET price=%s, price_cents=%s, updated_at=%s
            WHERE id=%s AND top='bead' AND enabled=1
            """,
            [
                (f"{row['new_price']:.2f}", row["new_price_cents"], timestamp, row["id"])
                for row in rows
            ],
        )

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
                    "batch_initial_price",
                    "material_price_batch",
                    table,
                    "codex",
                    "Codex",
                    f"初始化 {len(rows)} 个启用珠子 SKU 价格（{RULE_VERSION}）",
                    json.dumps({"backup_table": table}, ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False),
                    timestamp,
                ),
            )
    return table


def verify_applied(connection, expected_rows: list[dict[str, Any]]) -> None:
    with connection.cursor() as cursor:
        actual_rows = build_pricing_rows(fetch_active_beads(cursor))
    expected = {row["id"]: (row["new_price"], row["new_price_cents"]) for row in expected_rows}
    actual = {
        row["id"]: (Decimal(str(row["price"])).quantize(Decimal("0.00")), int(row["price_cents"]))
        for row in actual_rows
    }
    if actual != expected:
        raise ValueError("落库后价格与预览不一致")
    for series in SERIES_8MM_ANCHORS:
        prices = [expected[row["id"]][0] for row in expected_rows if row["series"] == series]
        if prices != sorted(prices) or len(set(prices)) != len(REQUIRED_SIZES):
            raise ValueError(f"{series} 的 8-15mm 价格没有严格递增")


def rollback_prices(connection, table: str) -> int:
    if not BACKUP_TABLE_RE.fullmatch(table):
        raise ValueError("仅允许使用本脚本生成的价格备份表")
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
        if total != EXPECTED_ACTIVE_SKUS:
            raise ValueError(f"备份行数异常: expected={EXPECTED_ACTIVE_SKUS}, actual={total}")
        cursor.execute(
            f"""
            UPDATE managed_materials AS m
            JOIN `{table}` AS b ON b.id=m.id
            SET m.price=b.price, m.price_cents=b.price_cents, m.updated_at=b.updated_at
            WHERE m.top='bead'
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为测试环境当前启用圆珠设置市场校准初始价")
    parser.add_argument("--apply", action="store_true", help="创建价格备份并在单事务中写入测试库")
    parser.add_argument("--rollback-table", help="从本脚本生成的备份表恢复价格")
    parser.add_argument("--export-csv", type=Path, help="导出逐 SKU 调价清单")
    args = parser.parse_args()
    if args.apply and args.rollback_table:
        parser.error("--apply 与 --rollback-table 不能同时使用")
    return args


def main() -> None:
    load_env_file(ROOT)
    args = parse_args()
    validate_test_environment()
    connection = connect_mysql()
    try:
        if args.rollback_table:
            restored = rollback_prices(connection, args.rollback_table)
            connection.commit()
            print(json.dumps({"restored": restored, "backup_table": args.rollback_table}, ensure_ascii=False))
            return

        with connection.cursor() as cursor:
            rows = build_pricing_rows(fetch_active_beads(cursor, lock=args.apply))
        if args.export_csv:
            export_csv(args.export_csv, rows)
        summary = pricing_summary(rows)
        if not args.apply:
            print(json.dumps({**summary, "mode": "dry-run"}, ensure_ascii=False, indent=2))
            return

        table = apply_prices(connection, rows)
        verify_applied(connection, rows)
        connection.commit()
        print(json.dumps({**summary, "mode": "applied", "backup_table": table}, ensure_ascii=False, indent=2))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
