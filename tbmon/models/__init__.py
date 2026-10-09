"""领域模型。

    from tbmon.models import ProductInfo, FetchReport, Money

- `product.py`  商品本身：Money / SkuInfo / ShopInfo / ProductInfo
- `report.py`   抓取过程记录：AttemptRecord / FetchReport / StateStatus

本模块只做再导出，方便调用方用一个入口拿到所有模型。
"""

from __future__ import annotations

from .product import Money, ProductInfo, ShopInfo, SkuInfo
from .report import AttemptRecord, FetchReport, StateStatus

__all__ = [
    "AttemptRecord",
    "FetchReport",
    "Money",
    "ProductInfo",
    "ShopInfo",
    "SkuInfo",
    "StateStatus",
]
