"""终端渲染：把抓取结果打成人类可读的报告。

与 `main.py` 分开的理由：渲染只关心「怎么显示」，命令装配只关心「怎么执行」，
两者变更频率完全不同（调对齐 / 加字段 vs 加子命令）。
"""

from __future__ import annotations

import sys
import unicodedata
from decimal import Decimal

from ..models import FetchReport, ProductInfo

EMPTY = "—"
#: 商品参数在终端里最多展示几项
_MAX_ATTRS = 6


def _width(text: str) -> int:
    """按终端显示宽度计算（中文占 2 列）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def format_money(value: Decimal | None, text: str | None = None) -> str:
    """金额渲染：无值时退化为原文，有原文且与数值不同则一并展示。"""
    if value is None:
        return text or EMPTY
    number = f"{value.quantize(Decimal('0.01')):,f}"
    if number.endswith(".00"):
        number = number[:-3]
    rendered = f"¥{number}"
    if text and text.strip() and text.strip() not in (number, rendered):
        return f"{rendered}（原文：{text.strip()}）"
    return rendered


def print_product(product: ProductInfo, report: FetchReport) -> None:
    """打印商品信息表。"""
    price = product.price
    sku_line = EMPTY
    if product.skus:
        sku_line = f"{len(product.skus)} 个"
        if price.is_range:
            sku_line += f"，区间 ¥{price.low} ~ ¥{price.high}"

    shop = product.shop
    shop_line = EMPTY
    if shop and (shop.name or shop.shop_id):
        shop_line = shop.name or "（未命名）"
        if shop.shop_id:
            shop_line += f"（shopId={shop.shop_id}）"

    attributes = EMPTY
    if product.attributes:
        attributes = "；".join(f"{k}={v}" for k, v in list(product.attributes.items())[:_MAX_ATTRS])

    rows: list[tuple[str, str]] = [
        ("商品ID", product.item_id),
        ("标题", product.title or EMPTY),
        ("当前价", format_money(price.current, price.current_text)),
        ("原价", format_money(price.original, price.original_text)),
        ("促销", "；".join(price.promotions) or EMPTY),
        ("SKU", sku_line),
        ("库存", str(product.stock_total) if product.stock_total is not None else EMPTY),
        ("已售", product.sold_text or EMPTY),
        ("店铺", shop_line),
        ("商品参数", attributes),
        ("主图", f"{len(product.images)} 张" if product.images else EMPTY),
        ("商品链接", product.url),
        ("数据来源", product.source),
        ("抓取耗时", f"{report.elapsed_ms} ms"),
    ]

    label_width = max(_width(label) for label, _ in rows) + 2
    print()
    for label, value in rows:
        print(f"{_pad(label, label_width)}{value}")


def print_diagnostics(report: FetchReport) -> None:
    """把告警与逐次尝试打到 stderr（不污染 stdout 的结构化输出）。"""
    for warning in report.warnings:
        print(f"  ! {warning}", file=sys.stderr)
    for attempt in report.attempts:
        flag = "ok " if attempt.ok else "fail"
        detail = f" — {attempt.error}" if attempt.error else ""
        print(f"  · [{flag}] {attempt.strategy} {attempt.elapsed_ms}ms{detail}", file=sys.stderr)


__all__ = ["EMPTY", "format_money", "print_diagnostics", "print_product"]
