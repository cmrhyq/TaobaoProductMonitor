"""解析入口：把原始响应装配成 `ProductInfo`。

按数据来源分派：
- `mtop-*` / `ssr-*`（接口与 SSR 数据同构）→ `parse_mtop`
- `dom*`（浏览器 DOM 兜底提取）            → `parse_dom`
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..errors import ParseError
from ..models import Money, ProductInfo, ShopInfo
from .extract import (
    collect_attributes,
    collect_price,
    collect_skus,
    norm_image,
    normalize_payload,
)
from .values import as_text, deep_get, find_first, parse_price_range, to_decimal


def parse_mtop(
    payload: Any,
    *,
    item_id: str,
    url: str,
    source: str,
    fetched_at: datetime | None = None,
) -> ProductInfo:
    """解析 mtop 系接口 / PC 页 SSR 的响应（两者结构同构）。"""
    data = normalize_payload(payload)
    item = deep_get(data, "item", {}) or deep_get(data, "itemVO", {}) or {}

    title = as_text(item.get("title")) if isinstance(item, dict) else None
    title = title or as_text(find_first(data, "title"))

    images: list[str] = []
    raw_images = item.get("images") if isinstance(item, dict) else None
    if not raw_images:
        raw_images = find_first(data, "images")
    if isinstance(raw_images, list):
        images = [img for img in (norm_image(i) for i in raw_images) if img]

    seller = deep_get(data, "seller", {}) or {}
    shop = None
    if isinstance(seller, dict) and (seller.get("shopName") or seller.get("sellerId")):
        shop_id = seller.get("shopId")
        shop = ShopInfo(
            shop_id=str(shop_id) if shop_id else None,
            seller_id=str(seller.get("sellerId")) if seller.get("sellerId") else None,
            name=as_text(seller.get("shopName")),
            url=f"https://shop{shop_id}.taobao.com" if shop_id else None,
        )

    money = collect_price(data)
    skus = collect_skus(data)
    sku_prices = [s.price for s in skus if s.price is not None]
    if sku_prices:
        money.low, money.high = min(sku_prices), max(sku_prices)
        if money.current is None:
            # 多 SKU 区间价商品没有统一实付价，退化为区间最低价
            money.current = money.low
            money.current_text = next((s.price_text for s in skus if s.price is not None), None)

    stock_values = [s.stock for s in skus if s.stock is not None]
    stock_total = sum(stock_values) if stock_values else None

    sold = find_first(data, "vagueSellCount") or find_first(data, "sellCount")
    sold_text = None
    if sold not in (None, ""):
        sold_str = str(sold).strip()
        sold_text = f"已售 {sold_str}" if sold_str.isdigit() else sold_str

    product = ProductInfo(
        item_id=item_id,
        url=url,
        title=title,
        subtitle=as_text(item.get("subtitle")) if isinstance(item, dict) else None,
        price=money,
        skus=skus,
        images=images,
        shop=shop,
        attributes=collect_attributes(data),
        stock_total=stock_total,
        sold_text=sold_text,
        source=source,
        fetched_at=fetched_at or datetime.now(),
    )

    if not product.title and product.price.current is None and not product.skus:
        raise ParseError("响应中未解析出标题、价格与规格（可能被要求登录或商品已下架）")
    return product


def parse_dom(
    payload: Any,
    *,
    item_id: str,
    url: str,
    source: str = "dom",
    fetched_at: datetime | None = None,
) -> ProductInfo:
    """解析浏览器 DOM 兜底抓取的结构（字段完整度低于接口数据）。"""
    if not isinstance(payload, dict):
        raise ParseError("DOM 抓取结果格式非法")

    price = Money(note="来自页面 DOM，优先级低于接口数据")
    candidates = payload.get("price_candidates") or []
    if candidates:
        best = candidates[0]
        text = best.get("text") if isinstance(best, dict) else str(best)
        price.current_text = text
        low, high = parse_price_range(text)
        price.current, price.low, price.high = low, low, high
    if payload.get("original_text"):
        price.original_text = str(payload["original_text"])
        price.original = to_decimal(price.original_text)

    title = as_text(payload.get("title"))
    images = [img for img in (norm_image(i) for i in payload.get("images") or []) if img]
    product = ProductInfo(
        item_id=item_id,
        url=url,
        title=title,
        price=price,
        images=images,
        shop=ShopInfo(name=as_text(payload.get("shop_name"))) if payload.get("shop_name") else None,
        attributes={str(k): str(v) for k, v in (payload.get("attributes") or {}).items()},
        source=source,
        fetched_at=fetched_at or datetime.now(),
    )
    if not product.title and product.price.current is None:
        raise ParseError("DOM 中也未找到价格与标题（可能未登录或页面结构已变）")
    return product


def parse(
    payload: Any,
    *,
    source: str,
    item_id: str,
    url: str,
    fetched_at: datetime | None = None,
) -> ProductInfo:
    """统一入口：按来源分派到对应解析器。"""
    if source.startswith("dom"):
        return parse_dom(payload, item_id=item_id, url=url, source=source, fetched_at=fetched_at)
    return parse_mtop(payload, item_id=item_id, url=url, source=source, fetched_at=fetched_at)


__all__ = ["parse", "parse_dom", "parse_mtop"]
