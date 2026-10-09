"""容错解析：原始响应 → `ProductInfo`。

    from tbmon.parsers import parse

    product = parse(payload, source="ssr-pc", item_id="123", url="https://...")

分层：
- `values.py`   通用取值工具（dict/list/标量），不含淘宝业务知识
- `extract.py`  淘宝业务字段抽取：价格 / SKU / 商品参数
- `detail.py`   装配入口：parse_mtop / parse_dom / parse
"""

from __future__ import annotations

from .detail import parse, parse_dom, parse_mtop
from .extract import (
    collect_attributes,
    collect_price,
    collect_skus,
    money_from_node,
    norm_image,
    normalize_payload,
    price_node_text,
)
from .values import as_text, deep_get, find_first, parse_price_range, to_decimal, to_int

__all__ = [
    "as_text",
    "collect_attributes",
    "collect_price",
    "collect_skus",
    "deep_get",
    "find_first",
    "money_from_node",
    "norm_image",
    "normalize_payload",
    "parse",
    "parse_dom",
    "parse_mtop",
    "parse_price_range",
    "price_node_text",
    "to_decimal",
    "to_int",
]
