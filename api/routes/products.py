"""
Product management endpoints.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data.repository.product_repo import ProductRepository, MONITOR_STATUS_NOT_STARTED

router = APIRouter()


class ProductCreate(BaseModel):
    """Request body for creating a product."""
    share_text: Optional[str] = None
    product_url: Optional[str] = None
    product_name: Optional[str] = None
    notify_email: str
    platform: str = "淘宝"


class ProductResponse(BaseModel):
    """Product response model."""
    product_id: int
    product_name: Optional[str]
    product_url: Optional[str]
    platform: Optional[str]
    monitor_status: int
    current_price: Optional[float]
    initial_price: Optional[float]
    lowest_price: Optional[float]
    check_count: int
    fail_count: int

    model_config = {"from_attributes": True}


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
        from service.monitor.taobao_monitor import TaobaoMonitor
        monitor = TaobaoMonitor()
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


@router.delete("/{product_id}")
def delete_product(product_id: int):
    """Delete a monitored product."""
    repo = ProductRepository()
    if not repo.delete_product(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted"}
