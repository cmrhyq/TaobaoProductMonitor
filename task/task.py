"""
Task scheduling and execution.
"""

import structlog

from data.repository.product_repo import ProductRepository
from service.monitor.taobao_monitor import TaobaoMonitor

logger = structlog.get_logger(__name__)


def product_monitor_task():
    """Execute a full monitoring cycle for all active products."""
    product_repo = ProductRepository()
    monitor = TaobaoMonitor()

    products = product_repo.query_monitor_products()
    logger.info("Monitor task started", product_count=len(products))

    success_count = 0
    fail_count = 0

    for product in products:
        try:
            if monitor.monitor_product(product):
                success_count += 1
            else:
                fail_count += 1
        except Exception as exc:
            fail_count += 1
            logger.error(
                "Product monitor failed",
                product_id=product.product_id,
                error=str(exc),
            )

    logger.info(
        "Monitor task completed",
        success=success_count,
        failed=fail_count,
        total=len(products),
    )


if __name__ == "__main__":
    product_monitor_task()
