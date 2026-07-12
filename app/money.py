from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


CENT = Decimal("0.01")
MAX_MONEY_CENTS = 99_999_999_999


def money_to_cents(value: Any, *, field_name: str = "金额", allow_zero: bool = True) -> int:
    if isinstance(value, bool) or value is None or value == "":
        raise ValueError(f"{field_name}格式无效")
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}格式无效") from exc
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        raise ValueError(f"{field_name}必须大于{'等于' if allow_zero else ''} 0")
    try:
        normalized = amount.quantize(CENT)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name}格式无效") from exc
    if amount != normalized:
        raise ValueError(f"{field_name}最多保留两位小数")
    cents = int(normalized * 100)
    if cents > MAX_MONEY_CENTS:
        raise ValueError(f"{field_name}超出允许范围")
    return cents


def cents_to_text(cents: Any) -> str:
    if isinstance(cents, bool):
        raise ValueError("金额分值格式无效")
    try:
        value = int(cents)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("金额分值格式无效") from exc
    if value < 0 or value > MAX_MONEY_CENTS:
        raise ValueError("金额分值超出允许范围")
    return f"{value // 100}.{value % 100:02d}"


def stored_cents(value: Any, *, field_name: str = "金额", allow_zero: bool = True) -> int:
    if isinstance(value, bool) or value is None or value == "":
        raise ValueError(f"{field_name}缺少有效整数分")
    try:
        decimal_value = Decimal(str(value))
        cents = int(decimal_value)
    except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field_name}整数分字段非法") from exc
    if decimal_value != Decimal(cents):
        raise ValueError(f"{field_name}整数分字段非法")
    if cents < 0 or (not allow_zero and cents == 0) or cents > MAX_MONEY_CENTS:
        raise ValueError(f"{field_name}整数分字段非法")
    return cents
