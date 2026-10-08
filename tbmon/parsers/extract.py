"""从详情数据里抽取「淘宝业务字段」：价格、SKU、商品参数。

稳定性策略：**不写死单一 schema**。
淘宝的详情接口在不同入口 / 不同灰度下字段路径会漂移（`price.priceText`、
`skuCore.sku2info.0.price.priceText`、`apiStack[0].value` 里再套一层 JSON 都出现过），
因此这里统一用「候选路径 + 广度优先兜底查找」的方式取值：
能取到就给值，取不到就给 None，绝不因为一个字段缺失而整体失败。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from ..errors import ParseError
from ..models import Money, SkuInfo
from .values import (
    as_text,
    deep_get,
    find_first,
    money_in_cents,
    parse_price_range,
    to_int,
)

_ORIGINAL_TITLES = ("原价", "划线价", "指导价", "专柜价", "吊牌价")
#: PC 页 componentsVO.extensionInfoVO 里承载"商品参数"的分组类型
_BASE_PROPS_TYPES = ("BASE_PROPS", "BASE_PARAMS", "PROPS", "PARAMS")
#: 通用兜底用的参数容器键
_ATTR_KEYS = (
    "productParams", "parameters", "pdsKeyValues", "props2", "itemProps", "specification",
)
#: 参数值长度上限，超过基本是营销文案而不是商品参数
_MAX_ATTR_LENGTH = 200


# --------------------------------------------------------------------- 节点级工具
def money_from_node(node: Any) -> Decimal | None:
    """从价格节点（dict / 标量）里取金额。"""
    if node is None:
        return None
    if isinstance(node, dict):
        text = node.get("priceText") or node.get("subPriceText")
        if isinstance(text, str) and text.strip():
            low, _ = parse_price_range(text)
            if low is not None:
                return low
        for key in ("priceMoney", "priceCent", "cent"):
            if (cents := money_in_cents(node.get(key))) is not None:
                return cents
        for key in ("price", "subPrice", "value"):
            if (nested := money_from_node(node.get(key))) is not None:
                return nested
        return None
    if isinstance(node, str):
        low, _ = parse_price_range(node)
        return low
    return money_in_cents(node)


def price_node_text(node: Any) -> str | None:
    """取价格节点的展示文案。"""
    if isinstance(node, dict):
        for key in ("priceText", "priceTitle", "subPriceText"):
            if text := as_text(node.get(key)):
                return text
    return as_text(node)


def kv_from_item(node: Any) -> tuple[str | None, str | None]:
    """把一条参数项归一成 (名称, 取值)。

    淘宝有三种写法：{name,value} / {propName,propValue} / {title, text: [...]}
    """
    if not isinstance(node, dict):
        return None, None
    name = node.get("title") or node.get("name") or node.get("propName") or node.get("key")
    raw = node.get("text") or node.get("value") or node.get("propValue")
    if isinstance(raw, list):
        value = " / ".join(str(x) for x in raw if x not in (None, ""))
    else:
        value = str(raw) if raw not in (None, "") else None
    return (str(name) if name else None), (value or None)


def iter_kv(node: Any) -> Iterator[tuple[str, str]]:
    """从参数容器里迭代 (名称, 取值)，跳过 SKU 属性定义。"""
    if isinstance(node, dict):
        if "values" in node and any(
            isinstance(v, dict) and "vid" in v for v in (node.get("values") or [])
        ):
            return  # skuBase.props 的形态，不是商品参数
        name, value = kv_from_item(node)
        if name and value:
            yield name, value
        return
    if isinstance(node, list):
        for entry in node:
            yield from iter_kv(entry)


def norm_image(url: Any) -> str | None:
    """图片地址归一：补齐协议头，丢弃无法识别的内容。"""
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return None


# --------------------------------------------------------------------- 容器归一
def normalize_payload(payload: Any) -> dict[str, Any]:
    """把响应收敛成"详情数据字典"。

    兼容三种形态：
      1. mtop 直接返回的数据对象
      2. 外层带 data 包装
      3. apiStack[0].value 里再套一层 JSON 字符串
    """
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ParseError("响应不是 JSON 对象")

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    merged: dict[str, Any] = dict(data)

    for stack in merged.get("apiStack") or []:
        if isinstance(stack, dict):
            raw = stack.get("value")
            if isinstance(raw, str) and raw.strip().startswith("{"):
                try:
                    inner = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(inner, dict):
                    for key, value in inner.items():
                        merged.setdefault(key, value)
    return merged


# --------------------------------------------------------------------- 字段抽取
def collect_price(data: dict[str, Any]) -> Money:
    """抽取价格。

    实网确认的两种 schema：
      1. PC 页 / 新接口：`skuCore.sku2info["0"].subPrice` 是**实付价**（"店铺优惠后"），
         `...price` 是**优惠前 / 列表价** → 前者才是 current，后者是 original；
      2. 老接口：`price.price` 就是当前价，原价放在 `price.extraPrices`。
    两种都要支持，否则会把"优惠前价"当成实付价（曾踩过）。
    """
    summary = deep_get(data, "skuCore.sku2info.0", {}) or {}
    sub_node = summary.get("subPrice") if isinstance(summary, dict) else None
    list_node = summary.get("price") if isinstance(summary, dict) else None
    price_block = deep_get(data, "price", {}) or {}
    block_node = price_block.get("price") if isinstance(price_block, dict) else None

    current = money_from_node(sub_node) or money_from_node(block_node) or money_from_node(list_node)
    current_text = (
        price_node_text(sub_node) or price_node_text(block_node) or price_node_text(list_node)
    )

    original: Decimal | None = None
    original_text: str | None = None
    if sub_node is not None:
        # 有实付价时，列表价就是优惠前价
        original = money_from_node(list_node)
        original_text = price_node_text(list_node)

    if current is None:
        fallback = find_first(data, "priceText")
        if fallback is not None:
            current_text = price_node_text(fallback) or current_text
            current = money_from_node(fallback)
            if current is None and isinstance(fallback, str):
                current, _ = parse_price_range(fallback)

    if current is None:
        raw = find_first(data, "price")
        if isinstance(raw, (int, float, str)):
            current_text = current_text or str(raw)
            current = money_from_node(raw)

    promotions: list[str] = []
    if isinstance(sub_node, dict):
        title = as_text(sub_node.get("priceTitle"))
        if title:
            promotions.append(f"{title}{current_text or ''}".strip())

    for entry in deep_get(price_block, "extraPrices", []) or []:
        text = price_node_text(entry) or ""
        title = ""
        if isinstance(entry, dict):
            title = str(entry.get("priceTitle") or entry.get("type") or "")
        label = f"{title} {text}".strip()
        if any(k in title for k in _ORIGINAL_TITLES) and original is None:
            original = money_from_node(entry)
            original_text = text or None
        elif label:
            promotions.append(label)

    money = Money(
        current=current,
        current_text=current_text,
        original=original,
        original_text=original_text,
        promotions=list(dict.fromkeys(promotions)),
    )
    if money.current is not None:
        money.low = money.high = money.current
    if current_text and "起" in current_text:
        money.note = "为多规格起步价，实际以下单规格为准"
    return money


def collect_skus(data: dict[str, Any]) -> list[SkuInfo]:
    """抽取 SKU 列表（规格组合 → 价格 / 库存）。"""
    sku_base = deep_get(data, "skuBase", {}) or {}
    sku_info = deep_get(data, "skuCore.sku2info", {}) or {}
    if not isinstance(sku_base, dict) or not isinstance(sku_info, dict):
        return []

    prop_names: dict[str, str] = {}
    value_names: dict[tuple[str, str], str] = {}
    for prop in sku_base.get("props") or []:
        if not isinstance(prop, dict):
            continue
        pid = str(prop.get("pid") or "")
        prop_names[pid] = str(prop.get("name") or pid)
        for value in prop.get("values") or []:
            if isinstance(value, dict):
                value_names[(pid, str(value.get("vid") or ""))] = str(value.get("name") or "")

    skus: list[SkuInfo] = []
    for entry in sku_base.get("skus") or []:
        if not isinstance(entry, dict):
            continue
        sku_id = str(entry.get("skuId") or "")
        props: dict[str, str] = {}
        for pair in str(entry.get("propPath") or "").split(";"):
            if ":" not in pair:
                continue
            pid, vid = pair.split(":", 1)
            # "-1:-1" 是"无该维度"的占位，必须跳过，否则会多出一个 "-1" 属性
            if pid in ("", "-1") or vid in ("", "-1"):
                continue
            name = prop_names.get(pid)
            if not name:
                continue
            props[name] = value_names.get((pid, vid), vid)

        info = sku_info.get(sku_id) or {}
        info = info if isinstance(info, dict) else {}
        sub_node = info.get("subPrice")
        list_node = info.get("price")
        skus.append(
            SkuInfo(
                sku_id=sku_id,
                props=props,
                price=money_from_node(sub_node) or money_from_node(list_node),
                original_price=money_from_node(list_node) if sub_node is not None else None,
                price_text=price_node_text(sub_node) or price_node_text(list_node),
                stock=to_int(info.get("quantity")),
            )
        )
    return skus


def collect_attributes(data: dict[str, Any]) -> dict[str, str]:
    """抽取商品参数。

    优先走 PC 页的结构化分组（`componentsVO.extensionInfoVO.infos[type=BASE_PROPS]`），
    避免把"优惠 / 保障"等营销文案误当成商品参数；再去通用容器里兜底。
    """
    attributes: dict[str, str] = {}

    for group in deep_get(data, "componentsVO.extensionInfoVO.infos", []) or []:
        if not isinstance(group, dict):
            continue
        if str(group.get("type") or "").upper() not in _BASE_PROPS_TYPES:
            continue
        for item in group.get("items") or []:
            name, value = kv_from_item(item)
            if name and value and len(value) < _MAX_ATTR_LENGTH:
                attributes.setdefault(name, value)

    if attributes:
        return attributes

    for key in _ATTR_KEYS:
        node = find_first(data, key)
        if node is None:
            continue
        for name, value in iter_kv(node):
            if name and value and len(value) < _MAX_ATTR_LENGTH:
                attributes.setdefault(name, value)
    return attributes


__all__ = [
    "collect_attributes",
    "collect_price",
    "collect_skus",
    "iter_kv",
    "kv_from_item",
    "money_from_node",
    "norm_image",
    "normalize_payload",
    "price_node_text",
]
