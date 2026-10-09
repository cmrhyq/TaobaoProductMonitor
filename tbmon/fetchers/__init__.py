"""抓取策略集合。

    from tbmon.fetchers import FetchOutcome, available_strategies

- `base.py`      策略公共契约：Fetcher 协议 / FetchOutcome / RateLimiter / JSONP 剥壳
- `registry.py`  策略注册表与优先级（新增策略只改这里）
- `scripts.py`   注入浏览器的 JavaScript 片段
- `browser.py`   浏览器策略：PC 详情页 SSR → 接口截获 → DOM
- `mtop_http.py` HTTP 策略：直连 mtop（实测被风控，保留作机会性尝试）
"""

from __future__ import annotations

from .base import Fetcher, FetchOutcome, RateLimiter, decode_jsonp
from .browser import BrowserDetailFetcher
from .mtop_http import MtopHttpFetcher
from .registry import (
    REGISTRY,
    STRATEGY_ORDER,
    StrategyContext,
    available_strategies,
    build_fetcher,
)

__all__ = [
    "REGISTRY",
    "STRATEGY_ORDER",
    "BrowserDetailFetcher",
    "FetchOutcome",
    "Fetcher",
    "MtopHttpFetcher",
    "RateLimiter",
    "StrategyContext",
    "available_strategies",
    "build_fetcher",
    "decode_jsonp",
]
