"""
Product snapshot repository - data access for the product_snapshot table.

Stores the full detail payload returned by a fetch (price / skus / attributes /
shop / images) so the rich data is not lost after a monitoring cycle.

The repository deliberately does not import tbmon at runtime: it duck-types the
ProductInfo object, keeping the persistence layer independent from the scraper.
"""

import json
from typing import TYPE_CHECKING, Any

import structlog

from data.database import get_session
from data.models import ProductSnapshot

if TYPE_CHECKING:  # pragma: no cover - typing only
    from tbmon.models import ProductInfo

logger = structlog.get_logger(__name__)


def _dumps(value: Any) -> str | None:
    """Serialize to JSON text; None stays None so the column is NULL not 'null'."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _as_dict(model: Any) -> dict | None:
    """pydantic model → plain json-safe dict (Decimals/datetimes become strings)."""
    if model is None:
        return None
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return dict(model)


def _as_float(value: Any) -> float | None:
    return None if value is None else float(value)


class SnapshotRepository:
    """Data access for product_snapshot table using SQLAlchemy ORM."""

    def insert_snapshot(
        self,
        product_id: int,
        product: "ProductInfo",
        *,
        extra_warnings: list[str] | None = None,
    ) -> int | None:
        """Persist one full fetch result. Returns snapshot_id, or None on failure."""
        price = getattr(product, "price", None)
        shop = getattr(product, "shop", None)

        try:
            with get_session() as session:
                record = ProductSnapshot(
                    product_id=product_id,
                    item_id=getattr(product, "item_id", None),
                    title=getattr(product, "title", None),
                    subtitle=getattr(product, "subtitle", None),
                    price_current=_as_float(getattr(price, "current", None)),
                    price_original=_as_float(getattr(price, "original", None)),
                    price_low=_as_float(getattr(price, "low", None)),
                    price_high=_as_float(getattr(price, "high", None)),
                    price_text=getattr(price, "current_text", None),
                    promotions_json=_dumps(getattr(price, "promotions", None)),
                    stock_total=getattr(product, "stock_total", None),
                    sold_text=getattr(product, "sold_text", None),
                    skus_json=_dumps([_as_dict(s) for s in (getattr(product, "skus", None) or [])]),
                    attributes_json=_dumps(getattr(product, "attributes", None)),
                    images_json=_dumps(getattr(product, "images", None)),
                    shop_json=_dumps(_as_dict(shop)),
                    shop_name=getattr(shop, "name", None) if shop is not None else None,
                    source=getattr(product, "source", None),
                    fetched_at=getattr(product, "fetched_at", None),
                )
                session.add(record)
                session.flush()
                return record.snapshot_id
        except Exception as exc:
            logger.error("Insert snapshot failed", error=str(exc), product_id=product_id)
            return None

    def query_latest_snapshot(self, product_id: int) -> dict | None:
        """Most recent snapshot for a product (JSON fields already decoded)."""
        with get_session() as session:
            record = (
                session.query(ProductSnapshot)
                .filter(ProductSnapshot.product_id == product_id)
                .order_by(ProductSnapshot.snapshot_id.desc())
                .first()
            )
            return self._to_dict(record)

    def query_snapshot_history(self, product_id: int, limit: int = 30) -> list[dict]:
        """Recent snapshots, newest first."""
        with get_session() as session:
            records = (
                session.query(ProductSnapshot)
                .filter(ProductSnapshot.product_id == product_id)
                .order_by(ProductSnapshot.snapshot_id.desc())
                .limit(limit)
                .all()
            )
            return [d for d in (self._to_dict(r) for r in records) if d is not None]

    @staticmethod
    def _to_dict(record: ProductSnapshot | None) -> dict | None:
        if record is None:
            return None
        return {
            "snapshot_id": record.snapshot_id,
            "product_id": record.product_id,
            "item_id": record.item_id,
            "title": record.title,
            "subtitle": record.subtitle,
            "price": {
                "current": record.price_current,
                "original": record.price_original,
                "low": record.price_low,
                "high": record.price_high,
                "text": record.price_text,
                "promotions": _loads(record.promotions_json) or [],
            },
            "stock_total": record.stock_total,
            "sold_text": record.sold_text,
            "skus": _loads(record.skus_json) or [],
            "attributes": _loads(record.attributes_json) or {},
            "images": _loads(record.images_json) or [],
            "shop": _loads(record.shop_json),
            "shop_name": record.shop_name,
            "source": record.source,
            "fetched_at": record.fetched_at,
            "created_at": record.created_at,
        }
