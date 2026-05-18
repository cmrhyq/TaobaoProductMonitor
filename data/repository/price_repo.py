"""
Price history repository - data access for the price_history table.
"""

from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import func

from data.database import get_session
from data.models import PriceHistory

logger = structlog.get_logger(__name__)


class PriceRepository:
    """Data access for price_history table using SQLAlchemy ORM."""

    def insert_price(self, product_id: int, price: Decimal, fetch_method: str = "api") -> Optional[int]:
        """Record a price observation."""
        try:
            with get_session() as session:
                record = PriceHistory(
                    product_id=product_id,
                    price=float(price),
                    fetch_method=fetch_method,
                )
                session.add(record)
                session.flush()
                return record.history_id
        except Exception as e:
            logger.error("Insert price failed", error=str(e), product_id=product_id)
            return None

    def query_first_price(self, product_id: int) -> Optional[Decimal]:
        """Get the first recorded price for a product."""
        with get_session() as session:
            record = (
                session.query(PriceHistory.price)
                .filter(PriceHistory.product_id == product_id, PriceHistory.is_valid == 1)
                .order_by(PriceHistory.recorded_at.asc())
                .first()
            )
            if record:
                return Decimal(str(record.price))
            return None

    def query_latest_price(self, product_id: int) -> Optional[Decimal]:
        """Get the most recent price for a product."""
        with get_session() as session:
            record = (
                session.query(PriceHistory.price)
                .filter(PriceHistory.product_id == product_id, PriceHistory.is_valid == 1)
                .order_by(PriceHistory.recorded_at.desc())
                .first()
            )
            if record:
                return Decimal(str(record.price))
            return None

    def query_lowest_price(self, product_id: int) -> Optional[Decimal]:
        """Get the lowest recorded price for a product."""
        with get_session() as session:
            result = (
                session.query(func.min(PriceHistory.price))
                .filter(PriceHistory.product_id == product_id, PriceHistory.is_valid == 1)
                .scalar()
            )
            if result is not None:
                return Decimal(str(result))
            return None

    def query_price_history(self, product_id: int, limit: int = 30) -> list[dict]:
        """Get recent price history for a product."""
        with get_session() as session:
            records = (
                session.query(PriceHistory)
                .filter(PriceHistory.product_id == product_id, PriceHistory.is_valid == 1)
                .order_by(PriceHistory.recorded_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {"price": r.price, "fetch_method": r.fetch_method, "recorded_at": r.recorded_at}
                for r in records
            ]

    def query_price_count(self, product_id: int) -> int:
        """Count price records for a product."""
        with get_session() as session:
            return (
                session.query(func.count(PriceHistory.history_id))
                .filter(PriceHistory.product_id == product_id)
                .scalar() or 0
            )
