"""真实数据回归测试。

`fixtures/detail_ssr_real.json` 是从淘宝 PC 详情页 `window.__ICE_APP_CONTEXT__`
里**原样导出**的真实 SSR 数据（MUJI 靠垫 1050906790941）。

它的价值：字段路径、价格语义（subPrice=实付价 / price=优惠前价）、
SKU 的 `-1:-1` 占位、参数分组，全部是真实形态。
淘宝一旦调整结构，这些断言会立刻失败 —— 这正是我们要的哨兵。
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from tbmon.parsers import parse

FIXTURES = Path(__file__).parent / "fixtures"
ITEM_ID = "1050906790941"
SSR = json.loads((FIXTURES / "detail_ssr_real.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def product():
    return parse(SSR, source="ssr-pc", item_id=ITEM_ID,
                 url=f"https://item.taobao.com/item.htm?id={ITEM_ID}")


def test_title_and_basics(product) -> None:
    assert product.title == "MUJI 无印良品 柔软清凉棉多用途靠垫 55×40×20cm"
    assert product.item_id == ITEM_ID
    assert product.sold_text == "已售 4"
    assert len(product.images) == 5
    assert all(img.startswith("https://") for img in product.images)


def test_paid_price_is_sub_price_not_list_price(product) -> None:
    """这是最容易搞错的地方：subPrice（店铺优惠后）才是实付价。"""
    assert product.price.current == Decimal("382.00")
    assert product.price.original == Decimal("522.00")
    assert product.price.current_text == "382起"
    assert product.price.note is not None  # 起步价提示
    assert any("店铺优惠后" in p for p in product.price.promotions)


def test_multi_sku_range(product) -> None:
    assert product.price.low == Decimal("382.00")
    assert product.price.high == Decimal("420.00")


def test_skus_with_real_prop_path(product) -> None:
    assert len(product.skus) == 3
    by_props = {s.props.get("颜色分类"): s for s in product.skus}
    assert set(by_props) == {"象牙色", "灰色", "浅蓝色"}

    ivory = by_props["象牙色"]
    assert ivory.sku_id == "6249002683697"
    assert ivory.price == Decimal("382.00")
    assert ivory.original_price == Decimal("522.00")
    assert ivory.stock == 5

    # "-1:-1" 占位维度必须被丢弃，否则 props 里会多出一个 '-1'
    assert "-1" not in ivory.props
    assert all(all(k and not k.startswith("-") for k in s.props) for s in product.skus)


def test_stock_total_matches_summary(product) -> None:
    assert product.stock_total == 17


def test_shop_info(product) -> None:
    assert product.shop is not None
    assert product.shop.name == "天猫国际全球探物"
    assert product.shop.shop_id == "479456214"
    assert product.shop.seller_id == "4066234693"


def test_attributes_only_from_base_props(product) -> None:
    """商品参数只能来自 BASE_PROPS 分组，不能混入优惠/保障等营销文案。"""
    assert product.attributes["品牌"] == "MUJI/无印良品"
    assert product.attributes["商品品类"] == "靠垫"
    assert product.attributes["厚度(cm)"] == "20"
    assert "优惠" not in product.attributes
    assert all("官方立减" not in v for v in product.attributes.values())


def test_to_json_obj_is_serializable(product) -> None:
    dumped = json.loads(product.model_dump_json())
    assert dumped["item_id"] == ITEM_ID
    assert dumped["price"]["current"] == "382.00"
    assert isinstance(dumped["skus"], list)
