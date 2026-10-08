"""内嵌调度器测试。

不触发真实监控轮次：轮次函数一律注入假的。
"""

from __future__ import annotations

import threading

import schedule

from task.scheduler import MonitorScheduler, get_scheduler, start_scheduler, stop_scheduler
from task.task import get_run_state

SCHEDULER_THREAD = "monitor-scheduler"


class _MonitorCfg:
    def __init__(self, enabled=True, interval=60, on_startup=False) -> None:
        self.schedule_enabled = enabled
        self.interval_minutes = interval
        self.run_on_startup = on_startup


class _Settings:
    def __init__(self, **kwargs) -> None:
        self.monitor = _MonitorCfg(**kwargs)


def _thread_alive() -> bool:
    return any(t.name == SCHEDULER_THREAD and t.is_alive() for t in threading.enumerate())


def test_lifecycle_start_stop() -> None:
    scheduler = MonitorScheduler(1, job=lambda trigger: {"total": 0})

    assert scheduler.start() is True
    assert scheduler.is_running is True
    assert scheduler.next_run_at is not None
    assert _thread_alive() is True

    # 重复启动是空操作
    assert scheduler.start() is False

    scheduler.stop()
    assert scheduler.is_running is False
    assert scheduler.next_run_at is None
    assert _thread_alive() is False


def test_interval_has_a_floor_of_one_minute() -> None:
    assert MonitorScheduler(0).interval_minutes == 1
    assert MonitorScheduler(-5).interval_minutes == 1
    assert MonitorScheduler(30).interval_minutes == 30


def test_run_on_startup_fires_immediately() -> None:
    calls: list[str] = []
    scheduler = MonitorScheduler(60, run_on_startup=True, job=lambda trigger: calls.append(trigger))

    scheduler.start()
    try:
        assert calls == ["startup"]
    finally:
        scheduler.stop()


def test_injected_job_exception_is_swallowed_and_recorded() -> None:
    """调度线程绝不能因为轮次抛错而死掉——那会导致「服务活着却不再监控」。"""

    def boom(trigger: str) -> dict:
        raise RuntimeError("boom")

    scheduler = MonitorScheduler(1, job=boom)

    # 直接驱动内部执行路径，验证异常不逃逸
    scheduler._run_cycle("schedule")
    scheduler._run_cycle("schedule")

    state = get_run_state()
    assert state.last_error is not None
    assert "boom" in state.last_error


def test_scheduler_loop_survives_job_exception() -> None:
    def boom(trigger: str) -> dict:
        raise RuntimeError("boom")

    scheduler = MonitorScheduler(1, job=boom)
    scheduler.start()
    try:
        assert _thread_alive() is True
    finally:
        scheduler.stop()
    assert _thread_alive() is False


def test_other_schedule_users_are_not_disturbed() -> None:
    """只清理自己注册的任务，不干扰进程内其它 schedule 用法。"""
    foreign = schedule.every(1).hours.do(lambda: None).tag("someone-else")

    scheduler = MonitorScheduler(1, job=lambda trigger: {})
    scheduler.start()
    scheduler.stop()

    assert [job for job in schedule.get_jobs("someone-else")] == [foreign]
    schedule.clear("someone-else")


def test_start_scheduler_respects_disabled_config() -> None:
    assert start_scheduler(_Settings(enabled=False)) is None
    assert get_scheduler() is None


def test_start_scheduler_and_stop_scheduler_are_idempotent() -> None:
    first = start_scheduler(_Settings(enabled=True, interval=60))
    try:
        assert first is not None and first.is_running is True
        # 二次调用返回同一实例，不会起第二个线程
        assert start_scheduler(_Settings(enabled=True, interval=60)) is first
    finally:
        stop_scheduler()

    assert get_scheduler() is None
    stop_scheduler()  # 再停一次不应抛错
    assert _thread_alive() is False
