"""
Monitor control endpoints.

轮次状态（是否在跑 / 上轮结果 / 上轮错误）来自 `task.task` 的 RunState，
路由只读不造状态，避免出现两处真值。
"""

import threading

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import get_settings
from task.scheduler import get_scheduler
from task.task import get_run_state, is_running, product_monitor_task

logger = structlog.get_logger(__name__)

router = APIRouter()


class MonitorStatusResponse(BaseModel):
    """最近一轮监控的执行状态。"""

    running: bool
    trigger: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped_reason: str | None = None
    last_error: str | None = None


class ScheduleResponse(BaseModel):
    """内嵌调度器的状态。"""

    enabled: bool
    running: bool
    interval_minutes: int
    run_on_startup: bool
    next_run_at: str | None = None


def _run_cycle() -> None:
    product_monitor_task(trigger="manual")


@router.post("/trigger", response_model=dict)
def trigger_monitor():
    """Manually trigger a single monitoring cycle in the background.

    轮次互斥由 `product_monitor_task` 的非阻塞锁保证：即便两次触发擦肩而过，
    后到的那次也会直接空转返回，不会并发开两个浏览器。
    """
    if is_running():
        raise HTTPException(status_code=409, detail="监控轮次正在执行，请稍后查询 /monitor/status")

    thread = threading.Thread(target=_run_cycle, name="manual-monitor", daemon=True)
    thread.start()
    logger.info("Manual monitor cycle triggered")
    return {"message": "Monitor cycle triggered", "status": "running"}


@router.get("/status", response_model=MonitorStatusResponse)
def monitor_status():
    """查询最近一轮监控的状态与结果。"""
    return MonitorStatusResponse(**get_run_state().to_dict())


@router.get("/schedule", response_model=ScheduleResponse)
def monitor_schedule():
    """查询内嵌调度器的开关、间隔与下次执行时间。"""
    config = get_settings().monitor
    scheduler = get_scheduler()
    return ScheduleResponse(
        enabled=config.schedule_enabled,
        running=bool(scheduler and scheduler.is_running),
        interval_minutes=config.interval_minutes,
        run_on_startup=config.run_on_startup,
        next_run_at=scheduler.next_run_at if scheduler else None,
    )
