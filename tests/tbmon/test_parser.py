"""解析层测试：字段映射、价格归一化、schema 漂移兜底。"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from tbmon.errors import ParseError
from tbmon.parsers import (
    collect_skus,
    deep_get,
    find_first,
    normalize_payload,
    parse,
    parse_price_range,
    to_decimal,
)

FIXTURES = Path(__file__).parent / "fixtures"
ITEM_ID = "1050906790941"
URL = f"https://item.taobao.com/item.htm?id={ITEM_ID}"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ 工具函数
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("522", Decimal("522.00")),
        ("¥522.00", Decimal("522.00")),
        ("1,299.5元起", Decimal("1299.50")),
        (52200, Decimal("52200.00")),  # 纯数字按"元"处理；"分"的换算只在 priceMoney 字段上做
        ("暂无报价", None),
        (None, None),
    ],
)
def test_to_decimal(raw, expected) -> None:
    assert to_decimal(raw) == expected


def test_parse_price_range() -> None:
    assert parse_price_range("¥522") == (Decimal("522.00"), Decimal("522.00"))
    assert parse_price_range("522-598") == (Decimal("522.00"), Decimal("598.00"))


def test_deep_get_and_find_first() -> None:
    data = {"a": {"b": [{"c": 1}]}, "priceText": "x"}
    assert deep_get(data, "a.b.0.c") == 1
    assert deep_get(data, "a.z.0") is None
    assert find_first(data, "priceText") == "x"
    assert find_first(data, "missing") is None


# ------------------------------------------------------------------ 主解析
def test_parse_full_payload() -> None:
    product = parse(load("detail_mtop.json"), source="mtop-http", item_id=ITEM_ID, url=URL)

    assert product.item_id == ITEM_ID
    assert product.title.startswith("MUJI")
    assert product.price.current == Decimal("522.00")
    assert product.price.original == Decimal("598.00")
    assert product.price.low == Decimal("522.00")
    assert product.price.high == Decimal("598.00")
    assert any("券后价" in p for p in product.price.promotions)

    assert len(product.skus) == 2
    first = product.skus[0]
    assert first.sku_id == "4900000001"
    assert first.props == {"颜色分类": "米白"}
    assert first.price == Decimal("522.00")
    assert first.stock == 100

    assert product.stock_total == 128
    assert product.shop is not None
    assert product.shop.name == "无印良品MUJI官方旗舰店"
    assert product.shop.shop_id == "111222333"
    assert product.attributes.get("品牌") == "MUJI/无印良品"
    assert product.sold_text == "2000+"

    # 协议相对 URL 必须补全为 https，否则下游下载会失败
    assert all(img.startswith("https://") for img in product.images)
    assert len(product.images) == 2


def test_parse_api_stack_payload() -> None:
    product = parse(load("detail_apistack.json"), source="mtop-http", item_id=ITEM_ID, url=URL)
    assert product.title.startswith("MUJI")
    assert product.price.current == Decimal("522.00")


def test_normalize_payload_flattens_api_stack() -> None:
    data = normalize_payload(load("detail_apistack.json"))
    assert "item" in data and data["item"]["itemId"] == ITEM_ID


def test_parse_dom_fallback_payload() -> None:
    payload = {
        "title": "MUJI 无印良品 柔软清凉棉多用途靠垫",
        "price_candidates": [{"text": "¥522", "score": 12.0}, {"text": "¥598", "score": 1.0}],
        "original_text": "¥598",
        "shop_name": "无印良品旗舰店",
        "images": ["//img.alicdn.com/x.jpg"],
        "attributes": {},
    }
    product = parse(payload, source="dom-page", item_id=ITEM_ID, url=URL)
    assert product.price.current == Decimal("522.00")
    assert product.price.original == Decimal("598.00")
    assert product.shop and product.shop.name == "无印良品旗舰店"
    assert product.price.note is not None


def test_parse_raises_when_nothing_useful() -> None:
    with pytest.raises(ParseError):
        parse({"data": {"foo": "bar"}}, source="mtop-http", item_id=ITEM_ID, url=URL)


def test_collect_skus_tolerates_missing_fields() -> None:
    assert collect_skus({"skuBase": {"skus": []}}) == []
    assert collect_skus({}) == []
