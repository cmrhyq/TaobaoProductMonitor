"""浏览器会话：playwright 生命周期与上下文构造的唯一出口。

设计要点：**一处** 负责 playwright 的启动参数、上下文构造、storage_state 读写；
登录流程与抓取流程共用同一套构造逻辑，避免两处 UA / 视口配置漂移。

⚠️ playwright 的同步对象**禁止跨线程使用**：调用方必须在同一个线程内创建、
使用并关闭本会话，不要做成进程级单例供多线程共享。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from ..config import Settings
from ..errors import TbMonError
from .state import DOMAIN_KEYWORDS

log = logging.getLogger(__name__)


class BrowserSession:
    """playwright 生命周期与上下文构造的唯一出口。

    用法：
        with BrowserSession(settings) as session:
            fetcher = BrowserDetailFetcher(session, settings)
            fetcher.fetch(item_id)
    """

    def __init__(
        self,
        settings: Settings,
        *,
        storage_state: Path | str | None = None,
        headless: bool | None = None,
        mobile: bool = False,
        load_state: bool = True,
    ) -> None:
        self.settings = settings
        self.storage_state = Path(storage_state or settings.storage_state)
        self.headless = settings.headless if headless is None else headless
        self.mobile = mobile
        self.load_state = load_state
        self._pw = None
        self._browser = None
        self._context = None
        self._started_at: float | None = None

    # ---------------------------------------------------------------- 生命周期
    def start(self) -> BrowserSession:
        """启动浏览器并建好上下文；幂等，重复调用直接返回自身。"""
        if self._browser is not None:
            return self

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - 依赖缺失
            raise TbMonError(
                "缺少 playwright，请执行：pip install playwright && playwright install chromium"
            ) from exc

        self._pw = sync_playwright().start()
        launch_kwargs: dict = {
            # AutomationControlled 是 headless 被识别的典型特征，显式关掉
            "headless": self.headless,
            "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        }
        if proxy := self.settings.playwright_proxy():
            launch_kwargs["proxy"] = proxy
        self._browser = self._pw.chromium.launch(**launch_kwargs)

        context_kwargs: dict = {"locale": "zh-CN", "timezone_id": "Asia/Shanghai"}
        if self.mobile:
            context_kwargs.update(
                user_agent=self.settings.mobile_ua,
                viewport={"width": 414, "height": 896},
                is_mobile=True,
                has_touch=True,
            )
        else:
            context_kwargs.update(
                user_agent=self.settings.desktop_ua,
                viewport={"width": 1440, "height": 900},
            )

        if self.load_state and self.storage_state.exists():
            context_kwargs["storage_state"] = str(self.storage_state)

        self._context = self._browser.new_context(**context_kwargs)
        self._context.set_default_timeout(self.settings.nav_timeout_ms)
        self._started_at = time.time()
        return self

    def close(self) -> None:
        """关闭上下文与浏览器；幂等，异常一律吞掉（收尾失败不该影响主流程）。"""
        for closer in (self._context, self._browser):
            try:
                if closer is not None:
                    closer.close()
            except Exception:  # pragma: no cover
                pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:  # pragma: no cover
            pass
        self._pw = self._browser = self._context = None

    def __enter__(self) -> BrowserSession:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------------------------------------------------------------- 能力
    @property
    def context(self):
        """当前浏览器上下文；未 start() 时抛错而不是返回 None。"""
        if self._context is None:
            raise TbMonError("BrowserSession 尚未 start()")
        return self._context

    def new_page(self):
        """开一个新标签页。"""
        return self.context.new_page()

    def cookies(self) -> dict[str, str]:
        """当前淘宝域 cookie。"""
        return {
            c["name"]: c["value"]
            for c in self.context.cookies()
            if any(key in c.get("domain", "") for key in DOMAIN_KEYWORDS)
        }

    def is_logged_in(self) -> bool:
        """是否已登录：以关键会话 cookie 是否存在为准，而不是看 URL。"""
        cookies = self.cookies()
        return bool(cookies.get("unb")) and bool(cookies.get("cookie2") or cookies.get("_nk_"))

    def save_storage_state(self, path: Path | str | None = None) -> Path:
        """把当前登录态落盘，返回写入路径。"""
        target = Path(path or self.storage_state)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(target))
        return target


__all__ = ["BrowserSession"]
