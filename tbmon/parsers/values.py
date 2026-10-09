"""通用取值工具：与「淘宝业务字段」无关的纯数据搬运。

拆分理由：这些函数只依赖 `dict` / `list` / 标量，任何解析器都能复用，
放在业务抽取模块里会让「通用能力」和「淘宝 schema 知识」混在一起。
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_MONEY_RE = re.compile(r"\d+(?:\.\d+)?")
#: 金额统一保留到分
_CENTS = Decimal("0.01")


def deep_get(obj: Any, path: str, default: Any = None) -> Any:
    """按点号路径取值，任一层缺失返回 default。

    >>> deep_get({"a": {"b": [1, 2]}}, "a.b.1")
    2
    """
    current = obj
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return current


def find_first(obj: Any, key: str) -> Any:
    """广度优先查找第一个非空 key，用于 schema 漂移时的兜底。

    淘宝不同入口的字段嵌套深度不一，逐个写路径不现实；这里按层序找第一个
    非空的同名 key，能取到就用，取不到返回 None。
    """
    queue: list[Any] = [obj]
    while queue:
        node = queue.pop(0)
        if isinstance(node, dict):
            value = node.get(key)
            if value not in (None, "", [], {}):
                return value
            queue.extend(node.values())
        elif isinstance(node, list):
            queue.extend(node)
    return None


def as_text(value: Any) -> str | None:
    """非空字符串归一，其余一律 None。"""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def to_decimal(value: Any) -> Decimal | None:
    """把任意金额表示转成 Decimal；支持 '¥522'、'522.00元起'、'1,299'。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(_CENTS)
    if isinstance(value, str):
        match = _MONEY_RE.search(value.replace(",", ""))
        if match:
            try:
                return Decimal(match.group(0)).quantize(_CENTS)
            except InvalidOperation:  # pragma: no cover - 正则已保证可解析
                return None
    return None


def parse_price_range(text: str | None) -> tuple[Decimal | None, Decimal | None]:
    """解析价格文案：'522' / '¥522.00' / '522-598' / '39.9起' → (low, high)。"""
    if not text:
        return None, None
    numbers = [to_decimal(n) for n in _MONEY_RE.findall(text.replace(",", ""))]
    numbers = [n for n in numbers if n is not None]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return min(numbers), max(numbers)


def money_in_cents(value: Any) -> Decimal | None:
    """接口里的 `priceMoney` 等字段单位是「分」。"""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (Decimal(str(value)) / 100).quantize(_CENTS)
    return None


def to_int(value: Any) -> int | None:
    """库存等字段在接口里可能是 int，也可能是 '128' 这样的字符串。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text.isdigit():
            return int(text)
    return None


__all__ = [
    "as_text",
    "deep_get",
    "find_first",
    "money_in_cents",
    "parse_price_range",
    "to_decimal",
    "to_int",
]
