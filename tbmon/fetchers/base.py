"""抓取策略的公共契约。

一个新策略 = 实现 `Fetcher` 协议 + 在 `service.ItemService` 的构造表里注册一行，
不需要改动编排逻辑。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

#: mtop 的 JSONP 包装：`mtopjsonp1({...});` / `mtopjsonppcdetail2({...})`
_JSONP_RE = re.compile(r"^\s*(?:[\w$.]+\s*\()?\s*(\{.*\})\s*\)?\s*;?\s*$", re.S)


def decode_jsonp(text: str) -> Any:
    """解析 mtop 响应：可能是纯 JSON，也可能是 JSONP 包装。

    实际抓包发现 PC 页面的接口用的是 JSONP（`mtopjsonp1({...})`），
    直接 `response.json()` 会失败，必须先剥壳。
    """
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = _JSONP_RE.match(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


@dataclass(slots=True)
class FetchOutcome:
    """策略返回的原始结果（未解析）。"""

    payload: Any
    #: 数据来源标识，决定用哪个解析器：mtop-* / ssr-* → parse_mtop，dom* → parse_dom
    source: str
    meta: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Fetcher(Protocol):
    """抓取策略协议。"""

    name: str

    def fetch(self, item_id: str) -> FetchOutcome: ...


class RateLimiter:
    """同域最小请求间隔，避免自己把自己送进风控。"""

    def __init__(self, min_interval_s: float) -> None:
        self.min_interval_s = max(0.0, min_interval_s)
        self._last_at = 0.0

    def wait(self) -> None:
        """必要时阻塞，保证两次请求间隔不小于配置值。"""
        if self.min_interval_s <= 0:
            return
        elapsed = time.monotonic() - self._last_at
        if elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last_at = time.monotonic()


__all__ = ["FetchOutcome", "Fetcher", "RateLimiter", "decode_jsonp"]
