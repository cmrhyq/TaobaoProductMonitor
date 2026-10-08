"""
Product management endpoints.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data.repository.price_repo import PriceRepository
from data.repository.product_repo import MONITOR_STATUS_NOT_STARTED, ProductRepository
from data.repository.snapshot_repo import SnapshotRepository

router = APIRouter()


class ProductCreate(BaseModel):
    """Request body for creating a product."""
    share_text: str | None = None
    product_url: str | None = None
    product_name: str | None = None
    notify_email: str
    platform: str = "淘宝"


class ProductResponse(BaseModel):
    """Product response model."""
    product_id: int
    product_name: str | None
    product_url: str | None
    platform: str | None
    monitor_status: int
    current_price: float | None
    initial_price: float | None
    lowest_price: float | None
    check_count: int
    fail_count: int

    model_config = {"from_attributes": True}


class PriceHistoryItem(BaseModel):
    """价格历史中的一条记录（price = 实付价，original_price = 优惠前价）。"""

    price: float | None = None
    original_price: float | None = None
    fetch_method: str | None = None
    recorded_at: datetime | None = None


class SnapshotResponse(BaseModel):
    """最近一次抓取的商品完整快照。

    price / skus / attributes / images / shop 为富数据，只在快照里保存。
    """

    snapshot_id: int
    product_id: int
    item_id: str | None = None
    title: str | None = None
    subtitle: str | None = None
    price: dict[str, Any]
    stock_total: int | None = None
    sold_text: str | None = None
    skus: list[dict[str, Any]] = []
    attributes: dict[str, Any] = {}
    images: list[Any] = []
    shop: dict[str, Any] | None = None
    shop_name: str | None = None
    source: str | None = None
    fetched_at: datetime | None = None
    created_at: datetime | None = None


@router.get("", response_model=list[ProductResponse])
def list_products():
    """Get all monitored products."""
    repo = ProductRepository()
    products = repo.get_all_products()
    return [ProductResponse.model_validate(p) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int):
    """Get a single product by ID."""
    repo = ProductRepository()
    product = repo.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.post("", response_model=dict)
def create_product(body: ProductCreate):
    """Add a new product to monitor."""
    if body.share_text:
        from service.monitor import TaobaoMonitor

        # save_product_info 不启动浏览器，with 只是统一资源收尾
        with TaobaoMonitor() as monitor:
            product_id = monitor.save_product_info(body.share_text, body.notify_email)
        if not product_id:
            raise HTTPException(status_code=400, detail="Failed to parse share text")
        return {"product_id": product_id, "message": "Product added successfully"}

    if not body.product_url or not body.product_name:
        raise HTTPException(status_code=400, detail="product_url and product_name required if share_text not provided")

    repo = ProductRepository()
    product_id = repo.insert_product(
        user_id=1,
        platform=body.platform,
        product_url=body.product_url,
        product_name=body.product_name,
        product_tk=None,
        item_id=None,
        notify_email=body.notify_email,
        monitor_status=MONITOR_STATUS_NOT_STARTED,
    )
    if not product_id:
        raise HTTPException(status_code=500, detail="Failed to insert product")

    from data.repository.rule_repo import RuleRepository
    RuleRepository().insert_rule(product_id, "absolute_drop", threshold_value=0.01)

    return {"product_id": product_id, "message": "Product added successfully"}


@router.get("/{product_id}/snapshot", response_model=SnapshotResponse)
def get_latest_snapshot(product_id: int):
    """最近一次抓取的完整商品快照（标题 / SKU / 参数 / 店铺 / 图片）。"""
    if not ProductRepository().get_product_by_id(product_id):
        raise HTTPException(status_code=404, detail="Product not found")

    snapshot = SnapshotRepository().query_latest_snapshot(product_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="No snapshot recorded yet")
    return SnapshotResponse(**snapshot)


@router.get("/{product_id}/history", response_model=list[PriceHistoryItem])
def get_price_history(product_id: int, limit: int = 30):
    """价格历史（默认最近 30 条，倒序）。"""
    if not ProductRepository().get_product_by_id(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return [PriceHistoryItem(**row) for row in PriceRepository().query_price_history(product_id, limit)]


@router.delete("/{product_id}")
def delete_product(product_id: int):
    """Delete a monitored product."""
    repo = ProductRepository()
    if not repo.delete_product(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted"}
