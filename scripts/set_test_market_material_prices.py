"""Set market-calibrated prices for every currently enabled test material SKU.

The bead rules extend the 2026-07-22 market-price profiles.  Accessories reuse
the 2026-07-23 per-piece rules.  Retired or incomplete disabled SKUs are
intentionally outside this commercial-price operation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import pymysql

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.set_initial_accessory_prices import price_for_accessory
from scripts.set_initial_bead_prices import SERIES_PRICE_PROFILES, SIZE_FACTORS_BY_CURVE


RULE_VERSION = "20260807-enabled-material-market-v1"
BACKUP_TABLE_RE = re.compile(r"^managed_enabled_material_price_backup_\d{8}_\d{6}$")

# Added after the original 39-series bead study.  These are conservative 8mm
# retail anchors in yuan, grouped by the same C/M/R size curves used in that study.
ADDITIONAL_BEAD_PRICE_PROFILES: dict[str, tuple[str, Decimal]] = {
    "灰兔毛": ("M", Decimal("9.5")),
    "蓝发晶": ("R", Decimal("9.0")),
    "千层幽灵": ("M", Decimal("9.0")),
    "抹茶幽灵": ("M", Decimal("9.0")),
    "绿幽灵满天星": ("M", Decimal("10.0")),
    "雪花幽灵": ("M", Decimal("7.5")),
    "冰川蓝": ("M", Decimal("6.0")),
    "圣蓝": ("M", Decimal("8.0")),
    "蓝天白云": ("C", Decimal("5.0")),
    "魔鬼蓝": ("M", Decimal("7.0")),
    "南红玛瑙": ("M", Decimal("6.5")),
    "樱花玛瑙": ("M", Decimal("5.5")),
    "盐源玛瑙": ("M", Decimal("7.0")),
    "墨晶": ("C", Decimal("4.0")),
    "浅茶": ("C", Decimal("3.0")),
    "深茶": ("C", Decimal("3.5")),
    "拉丝萤石": ("M", Decimal("5.5")),
    "紫萤石": ("C", Decimal("4.0")),
    "绿萤石": ("C", Decimal("4.0")),
    "羽毛萤石": ("M", Decimal("5.0")),
    "蓝萤石": ("C", Decimal("4.0")),
    "黄萤石": ("C", Decimal("4.0")),
}
BEAD_PRICE_PROFILES = {**SERIES_PRICE_PROFILES, **ADDITIONAL_BEAD_PRICE_PROFILES}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def half_yuan(value: Decimal) -> Decimal:
    return ((value * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2).quantize(Decimal("0.00"))


def price_cents(price: Decimal) -> int:
    return int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def size_factor(curve: str, size: int) -> Decimal:
    factors = SIZE_FACTORS_BY_CURVE[curve]
    if size in factors:
        return factors[size]
    if size == 7:
        return (factors[8] * factors[8] / factors[9]).quantize(Decimal("0.001"))
    if size > 15:
        last = factors[15]
        ratio = factors[15] / factors[14]
        return (last * (ratio ** (size - 15))).quantize(Decimal("0.001"))
    raise ValueError(f"未覆盖的珠径: {size}mm")


def bead_price(row: dict[str, Any]) -> Decimal:
    series = str(row.get("series") or "").strip()
    try:
        curve, anchor = BEAD_PRICE_PROFILES[series]
    except KeyError as exc:
        raise ValueError(f"品种没有市场定价锚点: {series}") from exc
    size_value = float(row.get("size") or 0)
    size = int(size_value)
    if size_value != size or size <= 0:
        raise ValueError(f"{series} 珠径无效: {size_value!r}")
    # 16/17mm 是此前已完成运营定价的特殊 SKU，保留其非占位历史价格。
    existing = Decimal(str(row.get("price") or 0)).quantize(Decimal("0.00"))
    if size > 15 and existing > Decimal("0.01"):
        return existing
    return half_yuan(anchor * size_factor(curve, size))


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
    if os.getenv("APP_ENV", "").strip().lower() not in {"test", "testing", "staging"} or "test" not in os.getenv("MYSQL_DATABASE", "").lower():
        raise SystemExit("拒绝非测试环境调价")


def fetch_enabled_materials(cursor, *, lock: bool) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, skuId, top, category, series, material_code, grade, name, size,
               price, price_cents, stock, enabled, updated_at
        FROM managed_materials
        WHERE enabled=1 AND top IN ('bead', 'accessory')
        ORDER BY top, category, series, size, id
        """ + (" FOR UPDATE" if lock else "")
    )
    return list(cursor.fetchall())


def build_pricing_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        top = str(row.get("top") or "")
        new_price = bead_price(row) if top == "bead" else price_for_accessory(row)
        result.append({
            **row,
            "old_price": Decimal(str(row.get("price") or 0)).quantize(Decimal("0.00")),
            "new_price": new_price,
            "new_price_cents": price_cents(new_price),
            "pricing_family": BEAD_PRICE_PROFILES[str(row.get("series") or "")][0] if top == "bead" else "accessory",
        })
    series = {str(row.get("series") or "") for row in result if row["top"] == "bead"}
    unexpected = sorted(series - set(BEAD_PRICE_PROFILES))
    if unexpected:
        raise ValueError(f"启用珠子缺少定价锚点: {unexpected}")
    return result


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_top: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_top.setdefault(str(row["top"]), []).append(row)
    return {
        "rule_version": RULE_VERSION,
        "scope": "enabled bead and accessory SKUs in test database",
        "sku_count": len(rows),
        "changed_count": sum(row["old_price"] != row["new_price"] or int(row.get("price_cents") or 0) != row["new_price_cents"] for row in rows),
        "by_top": {
            top: {
                "sku_count": len(items),
                "series_count": len({str(item.get("series") or "") for item in items}),
                "min_price": f"{min(item['new_price'] for item in items):.2f}",
                "max_price": f"{max(item['new_price'] for item in items):.2f}",
            }
            for top, items in by_top.items()
        },
    }


def backup_table_name() -> str:
    return f"managed_enabled_material_price_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def apply_prices(connection, rows: list[dict[str, Any]]) -> str:
    table = backup_table_name()
    if not BACKUP_TABLE_RE.fullmatch(table):
        raise ValueError("备份表名不安全")
    timestamp = now_iso()
    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE TABLE `{table}` AS SELECT id,price,price_cents,updated_at FROM managed_materials WHERE enabled=1 AND top IN ('bead','accessory')"
        )
        cursor.execute(f"ALTER TABLE `{table}` ADD PRIMARY KEY (id)")
        cursor.executemany(
            "UPDATE managed_materials SET price=%s,price_cents=%s,updated_at=%s,revision=revision+1 WHERE id=%s AND enabled=1",
            [(f"{row['new_price']:.2f}", row["new_price_cents"], timestamp, row["id"]) for row in rows],
        )
        cursor.execute("SHOW TABLES LIKE 'material_audit_logs'")
        if cursor.fetchone():
            cursor.execute(
                """INSERT INTO material_audit_logs
                (log_id,action,target_type,target_id,material_id,material_code,actor_id,actor_name,summary,before_json,after_json,created_at)
                VALUES (%s,%s,%s,%s,'','',%s,%s,%s,%s,%s,%s)""",
                (
                    f"matlog_{secrets.token_hex(12)}", "batch_market_price", "material_price_batch", table,
                    "codex", "Codex", f"按 {RULE_VERSION} 设置 {len(rows)} 个启用材料 SKU 市场价",
                    json.dumps({"backup_table": table}, ensure_ascii=False), json.dumps(summary(rows), ensure_ascii=False), timestamp,
                ),
            )
    return table


def rollback_prices(connection, table: str) -> int:
    if not BACKUP_TABLE_RE.fullmatch(table):
        raise ValueError("仅允许使用本脚本创建的材料价格备份表")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS count FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s",
            (table,),
        )
        if int(cursor.fetchone()["count"]) != 1:
            raise ValueError(f"价格备份表不存在: {table}")
        cursor.execute(f"SELECT COUNT(*) AS count FROM `{table}`")
        backup_count = int(cursor.fetchone()["count"])
        if backup_count <= 0:
            raise ValueError("价格备份表为空")
        cursor.execute(
            f"""
            UPDATE managed_materials AS material
            JOIN `{table}` AS backup ON backup.id=material.id
            SET material.price=backup.price,
                material.price_cents=backup.price_cents,
                material.updated_at=backup.updated_at,
                material.revision=material.revision+1
            """
        )
        cursor.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM managed_materials AS material
            JOIN `{table}` AS backup ON backup.id=material.id
            WHERE material.price<>backup.price
               OR COALESCE(material.price_cents,-1)<>COALESCE(backup.price_cents,-1)
               OR COALESCE(material.updated_at,'')<>COALESCE(backup.updated_at,'')
            """
        )
        if int(cursor.fetchone()["count"]) != 0:
            raise RuntimeError("价格回滚后校验失败")
    return backup_count


def verify(connection, rows: list[dict[str, Any]]) -> None:
    expected = {str(row["id"]): (row["new_price"], row["new_price_cents"]) for row in rows}
    with connection.cursor() as cursor:
        cursor.execute("SELECT id,price,price_cents FROM managed_materials WHERE enabled=1 AND top IN ('bead','accessory')")
        actual = {str(row["id"]): (Decimal(str(row["price"])).quantize(Decimal("0.00")), int(row["price_cents"] or 0)) for row in cursor.fetchall()}
    if actual != expected:
        raise RuntimeError("价格回读与定价规则不一致")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set market-calibrated prices for enabled test materials")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback-table")
    args = parser.parse_args()
    if args.apply and args.rollback_table:
        parser.error("--apply 与 --rollback-table 不能同时使用")
    validate_test_environment()
    connection = connect_mysql()
    try:
        if args.rollback_table:
            restored = rollback_prices(connection, args.rollback_table)
            connection.commit()
            print(json.dumps({"mode": "rolled-back", "restored": restored, "backup_table": args.rollback_table}, ensure_ascii=False))
            return
        with connection.cursor() as cursor:
            rows = build_pricing_rows(fetch_enabled_materials(cursor, lock=args.apply))
        payload: dict[str, Any] = {"mode": "dry-run", "summary": summary(rows)}
        if args.apply:
            payload["backup_table"] = apply_prices(connection, rows)
            verify(connection, rows)
            connection.commit()
            payload["mode"] = "applied"
        else:
            connection.rollback()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
