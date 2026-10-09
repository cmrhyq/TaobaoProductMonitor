"""抓取策略注册表。

新增一个抓取策略只需两步，**不需要改编排逻辑**：

1. 实现 `Fetcher` 协议（`fetch(item_id) -> FetchOutcome`）；
2. 在 `REGISTRY` 里加一行工厂函数，并按实际验证结果把它排进 `STRATEGY_ORDER`。

`STRATEGY_ORDER` 决定执行优先级 —— 实网结论：HTTP 直连必被风控 `RGV587`，
因此浏览器（PC 详情页 SSR）优先，HTTP 只做尾部机会性尝试。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping

from ..config import Settings
from ..session import BrowserSession, load_cookies, require_state
from .base import Fetcher, RateLimiter
from .browser import BrowserDetailFetcher
from .mtop_http import MtopHttpFetcher

log = logging.getLogger(__name__)


class StrategyContext:
    """策略之间共享的运行时资源。

    集中管理「浏览器会话」与「限速器」，让各策略工厂保持无状态：
    - 浏览器会话**按需启动**，且启动前先体检登录态 —— 登录态失效时直接抛
      `AuthRequiredError`，不白开一个 Chromium 去撞登录页；
    - 限速器全局唯一，避免多个策略各限各的、合起来仍然触发风控。
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._limiter = RateLimiter(settings.min_interval_s)
        self._session: BrowserSession | None = None

    @property
    def rate_limiter(self) -> RateLimiter:
        return self._limiter

    @property
    def session(self) -> BrowserSession | None:
        """已启动的浏览器会话；未启动时为 None（只读观测用）。"""
        return self._session

    def browser_session(self) -> BrowserSession:
        """取浏览器会话，必要时启动（幂等）。"""
        require_state(self.settings)
        if self._session is None:
            self._session = BrowserSession(self.settings).start()
        return self._session

    def close(self) -> None:
        """释放浏览器资源；幂等。"""
        if self._session is not None:
            try:
                self._session.close()
            finally:
                self._session = None


#: 策略工厂签名：拿到配置与共享资源，产出一个抓取器
FetcherFactory = Callable[[Settings, StrategyContext], Fetcher]

#: 执行优先级（从高到低）
STRATEGY_ORDER: tuple[str, ...] = ("browser", "http")


def _make_browser(settings: Settings, ctx: StrategyContext) -> Fetcher:
    """浏览器策略：真实指纹 + PC 详情页 SSR。"""
    return BrowserDetailFetcher(ctx.browser_session(), settings)


def _make_http(settings: Settings, ctx: StrategyContext) -> Fetcher:
    """HTTP 策略：直连 mtop，复用登录态 cookie，实测必被风控（保留作机会性尝试）。"""
    return MtopHttpFetcher(
        settings, load_cookies(settings.storage_state), rate_limiter=ctx.rate_limiter
    )


REGISTRY: Mapping[str, FetcherFactory] = {
    "browser": _make_browser,
    "http": _make_http,
}


def available_strategies() -> tuple[str, ...]:
    """按优先级返回全部策略名。"""
    return STRATEGY_ORDER


def build_fetcher(strategy: str, settings: Settings, ctx: StrategyContext) -> Fetcher:
    """按策略名构造抓取器。

    Raises:
        ValueError: 策略名未注册。
    """
    factory = REGISTRY.get(strategy)
    if factory is None:
        raise ValueError(f"未知策略 {strategy!r}，可选：{list(STRATEGY_ORDER)}")
    return factory(settings, ctx)


def _assert_registry_consistent() -> None:
    """注册表与优先级顺序必须一一对应，防止"加了策略忘了排序"。"""
    missing = set(REGISTRY) - set(STRATEGY_ORDER)
    extra = set(STRATEGY_ORDER) - set(REGISTRY)
    if missing or extra:
        raise RuntimeError(
            f"策略注册表与 STRATEGY_ORDER 不一致：未排序={sorted(missing)}，未注册={sorted(extra)}"
        )


_assert_registry_consistent()


__all__ = [
    "FetcherFactory",
    "REGISTRY",
    "STRATEGY_ORDER",
    "StrategyContext",
    "available_strategies",
    "build_fetcher",
]
