"""扫码登录流程。

淘宝强制登录，而扫码必须有头浏览器，因此本函数是**阻塞**的：
调用方需要一直等到扫码成功或超时。

`on_event` 回调用于把进度透出去（CLI 打到终端、API 收进响应体），
本模块不关心它最终显示在哪里。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from ..config import Settings
from ..errors import AuthRequiredError
from .session import BrowserSession

LOGIN_URL = "https://login.taobao.com/member/login.jhtml"
#: 登录后预热这些站点，让淘宝下发 h5 域令牌（_m_h5_tk 等）
_WARMUP_URLS = ("https://www.taobao.com", "https://h5.m.taobao.com/")
#: 轮询登录态的间隔
_POLL_INTERVAL_MS = 1500
#: 进度提示的最小间隔（秒），避免刷屏
_TIP_INTERVAL_S = 30

EventCallback = Callable[[str], None]


def login(
    settings: Settings,
    *,
    timeout_s: int | None = None,
    on_event: EventCallback = print,
) -> Path:
    """打开浏览器让用户扫码登录，成功后落盘 storage_state。

    Args:
        settings: 运行配置
        timeout_s: 等待扫码的秒数，缺省取 `TB_LOGIN_TIMEOUT_S`
        on_event: 进度回调

    Returns:
        登录态文件路径。

    Raises:
        AuthRequiredError: 超时未获取到登录态。
    """
    timeout = timeout_s or settings.login_timeout_s
    on_event("正在打开浏览器，请使用淘宝 App 扫码登录（登录成功后窗口会自动关闭）…")

    with BrowserSession(settings, headless=False, mobile=False) as session:
        page = session.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        on_event("已打开登录页，等待扫码…")

        deadline = time.time() + timeout
        last_tip = 0.0
        while time.time() < deadline:
            if session.is_logged_in():
                on_event("登录成功，正在保存登录态…")
                break
            page.wait_for_timeout(_POLL_INTERVAL_MS)
            waited = time.time() - (deadline - timeout)
            if waited - last_tip >= _TIP_INTERVAL_S:
                last_tip = waited
                on_event(f"仍在等待扫码…（已等待 {int(waited)}s / {timeout}s）")
        else:
            raise AuthRequiredError(f"等待登录超时（{timeout}s），未获取到登录态")

        for warmup in _WARMUP_URLS:
            try:
                page.goto(warmup, wait_until="domcontentloaded", timeout=15_000)
            except Exception:  # pragma: no cover - 预热失败不阻断登录
                pass

        target = session.save_storage_state()
        on_event(f"登录态已保存：{target}")
        return target


__all__ = ["EventCallback", "LOGIN_URL", "login"]
