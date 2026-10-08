"""服务内嵌的定时监控调度器。

随 FastAPI 的 lifespan 启动与停止，用 `schedule` 库 + 一个常驻守护线程实现。
选择内嵌而非外部 cron 的原因：调度状态（下次执行时间、上轮结果）要能被
`GET /monitor/schedule` 与 `/monitor/status` 直接观测。

⚠️ 调度线程的异常必须全部吞下并登记：一旦线程静默死掉，服务看起来还在运行，
却再也不会监控——这是最难发现的故障模式。

⚠️ 必须单进程运行（uvicorn 单 worker）。多 worker 会让同一份调度被跑 N 次，
而且轮次互斥锁在进程内，跨进程无效。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime

import schedule
import structlog

from config.settings import Settings, get_settings
from task.task import product_monitor_task, record_error

logger = structlog.get_logger(__name__)

#: 只清理本调度器注册的任务，不干扰进程内其它 schedule 用法
_JOB_TAG = "tbmon-monitor"


class MonitorScheduler:
    """按固定间隔执行监控轮次的调度器。"""

    def __init__(
        self,
        interval_minutes: int,
        *,
        run_on_startup: bool = False,
        job: Callable[..., dict] | None = None,
    ) -> None:
        """
        Args:
            interval_minutes: 轮次间隔（分钟，最小 1）
            run_on_startup: 启动后是否立即先跑一轮
            job: 可注入的轮次函数（需接受 trigger 关键字参数），默认真实监控任务
        """
        self.interval_minutes = max(1, int(interval_minutes))
        self.run_on_startup = run_on_startup
        self._job = job or product_monitor_task
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -------------------------------------------------------------- 生命周期
    def start(self) -> bool:
        """启动调度线程；已在运行则不做任何事并返回 False。"""
        if self.is_running:
            logger.warning("Monitor scheduler already running")
            return False

        self._stop.clear()
        schedule.clear(_JOB_TAG)
        schedule.every(self.interval_minutes).minutes.do(self._tick).tag(_JOB_TAG)

        self._thread = threading.Thread(target=self._loop, name="monitor-scheduler", daemon=True)
        self._thread.start()
        logger.info(
            "Monitor scheduler started",
            interval_minutes=self.interval_minutes,
            run_on_startup=self.run_on_startup,
            next_run_at=self.next_run_at,
        )

        if self.run_on_startup:
            self._run_cycle("startup")
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """停止调度线程（幂等，可重复调用）。"""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():  # pragma: no cover - 仅当轮次仍在执行
                logger.warning("Monitor scheduler thread still busy, left as daemon")
            self._thread = None
        schedule.clear(_JOB_TAG)
        logger.info("Monitor scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def next_run_at(self) -> str | None:
        """下次计划执行时间（ISO 字符串）；未调度时为 None。"""
        jobs = schedule.get_jobs(_JOB_TAG)
        if not jobs or jobs[0].next_run is None:
            return None
        next_run: datetime = jobs[0].next_run
        return next_run.isoformat(timespec="seconds")

    # -------------------------------------------------------------- 内部
    def _tick(self) -> None:
        self._run_cycle("schedule")

    def _run_cycle(self, trigger: str) -> None:
        """执行一轮，保证异常不会逃逸到调度循环里。"""
        try:
            result = self._job(trigger=trigger)
            logger.info("Monitor cycle finished", trigger=trigger, **(result or {}))
        except Exception as exc:
            logger.exception("Monitor cycle crashed in scheduler", trigger=trigger)
            record_error(f"{type(exc).__name__}: {exc}")

    def _loop(self) -> None:
        while not self._stop.wait(1):
            try:
                schedule.run_pending()
            except Exception as exc:  # pragma: no cover - 防御性：绝不让线程死掉
                logger.exception("Scheduler loop error, continuing")
                record_error(f"scheduler: {type(exc).__name__}: {exc}")


# ------------------------------------------------------------------ 模块级单例
_scheduler: MonitorScheduler | None = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> MonitorScheduler | None:
    """当前调度器实例（未启用/未启动时为 None）。"""
    return _scheduler


def start_scheduler(settings: Settings | None = None) -> MonitorScheduler | None:
    """按配置启动内嵌调度器；`MONITOR_SCHEDULE_ENABLED=false` 时不启动。

    幂等：重复调用只会返回既有实例。
    """
    global _scheduler
    config = (settings or get_settings()).monitor
    if not config.schedule_enabled:
        logger.info("Monitor scheduler disabled by config")
        return None

    with _scheduler_lock:
        if _scheduler is not None and _scheduler.is_running:
            return _scheduler
        _scheduler = MonitorScheduler(
            config.interval_minutes, run_on_startup=config.run_on_startup
        )
        _scheduler.start()
        return _scheduler


def stop_scheduler() -> None:
    """停止并清理调度器（幂等）。"""
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.stop()
            _scheduler = None
