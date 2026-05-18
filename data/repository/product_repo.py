"""
Product repository - data access for the products table.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from data.database import get_session
from data.models import Product

logger = structlog.get_logger(__name__)

MONITOR_STATUS_NOT_STARTED = 10
MONITOR_STATUS_MONITORING = 11
MONITOR_STATUS_ENDED = 12


class ProductRepository:
    """Data access for products table using SQLAlchemy ORM."""

    def query_monitor_products(self) -> list[Product]:
        """Query products that need monitoring (status: NOT_STARTED or MONITORING)."""
        with get_session() as session:
            products = (
                session.query(Product)
                .filter(Product.monitor_status.in_([MONITOR_STATUS_NOT_STARTED, MONITOR_STATUS_MONITORING]))
                .all()
            )
            session.expunge_all()
            return products

    def get_product_by_id(self, product_id: int) -> Optional[Product]:
        """Get a single product by ID."""
        with get_session() as session:
            product = session.query(Product).filter(Product.product_id == product_id).first()
            if product:
                session.expunge(product)
            return product

    def get_all_products(self) -> list[Product]:
        """Get all products."""
        with get_session() as session:
            products = session.query(Product).all()
            session.expunge_all()
            return products

    def insert_product(
        self,
        user_id: int,
        platform: str,
        product_url: str,
        product_name: str,
        product_tk: Optional[str],
        item_id: Optional[str],
        notify_email: str,
        monitor_status: int = MONITOR_STATUS_NOT_STARTED,
    ) -> Optional[int]:
        """Insert a new product and return its ID."""
        try:
            with get_session() as session:
                product = Product(
                    user_id=user_id,
                    platform=platform,
                    product_url=product_url,
                    product_name=product_name,
                    product_tk=product_tk,
                    item_id=item_id,
                    notify_email=notify_email,
                    monitor_status=monitor_status,
                )
                session.add(product)
                session.flush()
                return product.product_id
        except Exception as e:
            logger.error("Insert product failed", error=str(e))
            return None

    def update_product_status(self, product_id: int, status: int) -> bool:
        """Update product monitoring status."""
        try:
            with get_session() as session:
                rows = (
                    session.query(Product)
                    .filter(Product.product_id == product_id)
                    .update({
                        Product.monitor_status: status,
                        Product.updated_at: datetime.now(),
                    })
                )
                return rows > 0
        except Exception as e:
            logger.error("Update product status failed", error=str(e), product_id=product_id)
            return False

    def update_product_prices(
        self,
        product_id: int,
        current_price: float,
        initial_price: Optional[float] = None,
        lowest_price: Optional[float] = None,
    ) -> bool:
        """Update price fields on the product."""
        try:
            with get_session() as session:
                updates = {
                    Product.current_price: current_price,
                    Product.last_check_at: datetime.now(),
                    Product.check_count: Product.check_count + 1,
                    Product.updated_at: datetime.now(),
                }
                if initial_price is not None:
                    updates[Product.initial_price] = initial_price
                if lowest_price is not None:
                    updates[Product.lowest_price] = lowest_price

                rows = (
                    session.query(Product)
                    .filter(Product.product_id == product_id)
                    .update(updates)
                )
                return rows > 0
        except Exception as e:
            logger.error("Update product prices failed", error=str(e), product_id=product_id)
            return False

    def increment_fail_count(self, product_id: int) -> bool:
        """Increment the failure counter."""
        try:
            with get_session() as session:
                rows = (
                    session.query(Product)
                    .filter(Product.product_id == product_id)
                    .update({
                        Product.fail_count: Product.fail_count + 1,
                        Product.updated_at: datetime.now(),
                    })
                )
                return rows > 0
        except Exception as e:
            logger.error("Increment fail count failed", error=str(e))
            return False

    def update_item_id(self, product_id: int, item_id: str) -> bool:
        """Store resolved item_id for a product."""
        try:
            with get_session() as session:
                rows = (
                    session.query(Product)
                    .filter(Product.product_id == product_id)
                    .update({
                        Product.item_id: item_id,
                        Product.updated_at: datetime.now(),
                    })
                )
                return rows > 0
        except Exception as e:
            logger.error("Update item_id failed", error=str(e))
            return False

    def delete_product(self, product_id: int) -> bool:
        """Delete a product by ID."""
        try:
            with get_session() as session:
                rows = session.query(Product).filter(Product.product_id == product_id).delete()
                return rows > 0
        except Exception as e:
            logger.error("Delete product failed", error=str(e))
            return False
