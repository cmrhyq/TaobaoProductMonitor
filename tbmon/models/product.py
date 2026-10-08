"""商品领域模型：抓取结果的最终产物。

约定：
- 金额统一用 `Decimal`（避免浮点误差），同时保留淘宝返回的原始文案 `*_text`；
- 抓不到的字段一律 `None`，不用 0 / "" 冒充，避免下游误判；
- 每个模型都能 `model_dump(mode="json")` 直接落库 / 落地。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Money(BaseModel):
    """价格：数值 + 原文 + 来源可信度。"""

    model_config = ConfigDict(extra="ignore")

    current: Decimal | None = Field(default=None, description="当前实付价（元）")
    current_text: str | None = Field(default=None, description="页面原文，如『¥522 券后』")
    original: Decimal | None = Field(default=None, description="划线价 / 原价（元）")
    original_text: str | None = None
    low: Decimal | None = Field(default=None, description="多 SKU 时的最低价")
    high: Decimal | None = Field(default=None, description="多 SKU 时的最高价")
    promotions: list[str] = Field(default_factory=list, description="促销/权益文案")
    currency: str = "CNY"
    note: str | None = Field(default=None, description="异常说明，例如『需登录查看』")

    @property
    def is_range(self) -> bool:
        """是否为区间价（多 SKU 且各规格价格不一致）。"""
        return self.low is not None and self.high is not None and self.low != self.high


class SkuInfo(BaseModel):
    """单个 SKU（规格组合）。"""

    model_config = ConfigDict(extra="ignore")

    sku_id: str
    props: dict[str, str] = Field(default_factory=dict, description="{颜色: 米白, 尺寸: 55×40cm}")
    price: Decimal | None = Field(default=None, description="实付价（有优惠时取优惠后价）")
    original_price: Decimal | None = Field(default=None, description="该 SKU 的优惠前价 / 划线价")
    price_text: str | None = None
    stock: int | None = None


class ShopInfo(BaseModel):
    """店铺信息。"""

    model_config = ConfigDict(extra="ignore")

    shop_id: str | None = None
    seller_id: str | None = None
    name: str | None = None
    url: str | None = None
    rating: str | None = Field(default=None, description="如『4.9 分』")
    location: str | None = None


class ProductInfo(BaseModel):
    """商品聚合信息（程序最终产物）。"""

    model_config = ConfigDict(extra="ignore")

    item_id: str
    url: str
    title: str | None = None
    subtitle: str | None = Field(default=None, description="卖点 / 副标题")
    price: Money = Field(default_factory=Money)
    skus: list[SkuInfo] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    shop: ShopInfo | None = None
    attributes: dict[str, str] = Field(default_factory=dict, description="商品参数")
    stock_total: int | None = None
    sold_text: str | None = Field(default=None, description="如『已售 2000+』")
    status_text: str | None = None
    source: str = Field(default="unknown", description="数据来源策略标识")
    fetched_at: datetime = Field(default_factory=datetime.now)

    def summary(self) -> str:  # pragma: no cover - 仅 CLI 展示
        """单行摘要。"""
        price = self.price.current_text or (str(self.price.current) if self.price.current else "未知")
        return f"[{self.item_id}] {self.title} | 价格 {price} | 来源 {self.source}"


__all__ = ["Money", "ProductInfo", "ShopInfo", "SkuInfo"]
