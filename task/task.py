"""
Monitor task execution - one full monitoring cycle over all active products.

设计要点：
- **前置登录态体检**：登录态失效时只提示一次并跳过本轮，避免 N 个商品各撞一次
  登录页、各耗尽一轮重试。
- **轮次互斥**：手动触发与定时调度可能同时到达，用非阻塞锁保证同一时刻只有一轮。
- **执行状态登记**：轮次进度/结果写入模块级 RunState，供 `GET /monitor/status` 读取；
  路由不自己造状态，避免两处真值。
- **线程亲和**：TaobaoMonitor（含 Playwright 浏览器会话）在本线程内创建并关闭，
  不做跨线程共享。
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, replace
from datetime import datetime

import structlog

from data.repository.product_repo import ProductRepository
from service.monitor import TaobaoMonitor

logger = structlog.get_logger(__name__)


@dataclass
class RunState:
    """最近一轮监控的执行状态。"""

    running: bool = False
    trigger: str | None = None          # manual / schedule / startup
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped_reason: str | None = None   # 本轮被跳过时的原因（如登录态失效）
    last_error: str | None = None       # 上一轮抛出的异常（含调度线程内部错误）

    def to_dict(self) -> dict:
        data = asdict(self)
        for key in ("started_at", "finished_at"):
            if data[key] is not None:
                data[key] = data[key].isoformat(timespec="seconds")
        return data


#: 轮次互斥：非阻塞获取，拿不到说明已有轮次在跑
_run_lock = threading.Lock()
_state_lock = threading.Lock()
_state = RunState()


def is_running() -> bool:
    """是否有监控轮次正在执行。"""
    return _run_lock.locked()


def get_run_state() -> RunState:
    """当前执行状态的快照（副本，调用方随意读）。"""
    with _state_lock:
        return replace(_state)


def record_error(message: str) -> None:
    """登记一个错误（供调度器记录线程内部异常）。"""
    with _state_lock:
        _state.last_error = message


def product_monitor_task(*, trigger: str = "manual") -> dict:
    """Execute a full monitoring cycle for all active products.

    Returns:
        本轮结果摘要 {total, success, failed, skipped}；已在执行时返回
        {"total": 0, "success": 0, "failed": 0, "skipped": "already_running"}。
    """
    if not _run_lock.acquire(blocking=False):
        logger.warning("Monitor cycle already running, skipping this trigger", trigger=trigger)
        return {"total": 0, "success": 0, "failed": 0, "skipped": "already_running"}

    with _state_lock:
        _state.running = True
        _state.trigger = trigger
        _state.started_at = datetime.now()
        _state.finished_at = None
        _state.total = _state.success = _state.failed = 0
        _state.skipped_reason = None
        _state.last_error = None

    try:
        return _run_cycle()
    except Exception as exc:
        logger.exception("Monitor cycle crashed", trigger=trigger)
        record_error(f"{type(exc).__name__}: {exc}")
        return {"total": 0, "success": 0, "failed": 0, "skipped": "crashed"}
    finally:
        with _state_lock:
            _state.running = False
            _state.finished_at = datetime.now()
        _run_lock.release()


def _run_cycle() -> dict:
    """单轮执行主体（调用方已持锁）。"""
    products = ProductRepository().query_monitor_products()
    if not products:
        logger.info("No product needs monitoring")
        with _state_lock:
            _state.skipped_reason = "no_products"
        return {"total": 0, "success": 0, "failed": 0, "skipped": "no_products"}

    with _state_lock:
        _state.total = len(products)

    with TaobaoMonitor() as monitor:
        status = monitor.login_state()
        if not status.ok:
            logger.error(
                "登录态不可用，跳过本轮监控（未逐个商品重试）",
                reason=status.reason,
                hint="请调用 POST /session/login 重新扫码登录",
            )
            with _state_lock:
                _state.skipped_reason = status.reason
            return {"total": len(products), "success": 0, "failed": 0, "skipped": "auth_required"}

        logger.info("Monitor task started", product_count=len(products), trigger=get_run_state().trigger)
        success = 0
        failed = 0

        for product in products:
            try:
                if monitor.monitor_product(product):
                    success += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    "Product monitor failed",
                    product_id=product.product_id,
                    error=f"{type(exc).__name__}: {exc}",
                )
            with _state_lock:
                _state.success = success
                _state.failed = failed

    logger.info("Monitor task completed", success=success, failed=failed, total=len(products))
    return {"total": len(products), "success": success, "failed": failed, "skipped": None}
