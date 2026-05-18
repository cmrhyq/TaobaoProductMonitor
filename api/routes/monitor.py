"""
Monitor control endpoints.
"""

import threading

from fastapi import APIRouter

import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/trigger")
def trigger_monitor():
    """Manually trigger a single monitoring cycle in the background."""
    def _run():
        from task.task import product_monitor_task
        product_monitor_task()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info("Manual monitor cycle triggered")
    return {"message": "Monitor cycle triggered", "status": "running"}
