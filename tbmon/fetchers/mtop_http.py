"""纯 HTTP 的 mtop 快速路径（约 0.5s，不开浏览器）。

mtop 的鉴权是三段式：
    1. 从 cookie 取 `_m_h5_tk`，用 `_` 切成 token
    2. `sign = md5(token & t & appKey & data)`
    3. 首次请求常常返回「令牌为空」，服务端同时下发新 `_m_h5_tk`，带着新 cookie 重发即可

注意：该路径在风控命中时会返回 `RGV587_ERROR`，此时**原地重试没有意义**，
直接抛 RiskControlError 让上层切换到浏览器策略。
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx

from ..config import Settings
from ..errors import AuthRequiredError, ParseError, RiskControlError, TbMonError, TransportError
from .base import FetchOutcome, RateLimiter

API_BASE = "https://h5api.m.taobao.com/h5"
#: (接口名, 版本, data 里的商品 ID 字段名)
CANDIDATES: tuple[tuple[str, str, str], ...] = (
    ("mtop.taobao.pcdetail.data.get", "1.0", "itemId"),
    ("mtop.taobao.detail.getdetail", "6.0", "itemNumId"),
)

_TOKEN_HINTS = ("TOKEN_EMPTY", "TOKEN_EXOIRED", "TOKEN_EXPIRED", "令牌为空", "令牌过期", "ILLEGAL_TOKEN")
_RISK_HINTS = ("RGV587", "USER_VALIDATE", "被挤爆", "FAIL_SYS_ILLEGAL_ACCESS", "FAIL_SYS_TRAFFIC_LIMIT")
_AUTH_HINTS = ("SESSION_EXPIRED", "SESSION_INVALID", "登录", "AUTH")


class MtopHttpFetcher:
    """直连 mtop 接口，最快但最容易被风控。"""

    name = "http"

    def __init__(
        self,
        settings: Settings,
        cookies: dict[str, str] | None = None,
        *,
        client: httpx.Client | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.settings = settings
        self._limiter = rate_limiter or RateLimiter(settings.min_interval_s)
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=settings.http_timeout_s,
            proxy=settings.proxy,
            cookies=cookies or {},
            headers={
                "User-Agent": settings.mobile_ua,
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "x-requested-with": "XMLHttpRequest",
                "Origin": "https://h5.m.taobao.com",
            },
        )

    def __enter__(self) -> MtopHttpFetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ------------------------------------------------------------------ 对外
    def fetch(self, item_id: str) -> FetchOutcome:
        errors: list[str] = []
        for api, version, id_key in CANDIDATES:
            try:
                payload, used_api = self._call(api, version, id_key, item_id)
                return FetchOutcome(payload=payload, source="mtop-http", meta={"api": used_api})
            except (RiskControlError, AuthRequiredError):
                raise
            except TbMonError as exc:
                errors.append(f"{api}: {exc}")
        raise ParseError("mtop 接口均未返回可解析数据", detail=" | ".join(errors))

    # ------------------------------------------------------------------ 内部
    def _call(self, api: str, version: str, id_key: str, item_id: str) -> tuple[Any, str]:
        data = json.dumps({id_key: item_id}, ensure_ascii=False, separators=(",", ":"))
        url = f"{API_BASE}/{api}/{version}/"
        headers = {"Referer": f"https://h5.m.taobao.com/awp/core/detail.htm?id={item_id}"}

        last_ret: list[str] = []
        for round_no in range(3):
            token = (self._client.cookies.get("_m_h5_tk") or "").split("_")[0]
            stamp = str(int(time.time() * 1000))
            params = {
                "jsv": "2.7.4",
                "appKey": self.settings.app_key,
                "t": stamp,
                "sign": self._sign(token, stamp, data),
                "api": api,
                "v": version,
                "type": "originaljson" if version.startswith("1.") else "json",
                "dataType": "json",
                "valueType": "string",
                "data": data,
            }
            self._limiter.wait()
            try:
                response = self._client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                raise TransportError(f"mtop 请求失败：{exc.__class__.__name__}") from exc

            if response.status_code >= 500:
                raise TransportError(f"mtop 返回 {response.status_code}")

            try:
                body = response.json()
            except json.JSONDecodeError as exc:
                raise ParseError("mtop 返回非 JSON", detail=response.text[:160]) from exc

            ret = [str(r) for r in body.get("ret") or []]
            last_ret = ret
            if any(r.startswith("SUCCESS") for r in ret):
                payload = body.get("data")
                if payload in (None, "", [], {}):
                    raise ParseError("mtop 返回成功但 data 为空")
                return payload, api

            # 令牌问题：服务端通常已下发新 _m_h5_tk，重发即可
            if any(hint in " ".join(ret) for hint in _TOKEN_HINTS) and round_no < 2:
                continue

            self._raise_for_ret(ret)

        raise ParseError("mtop 令牌校验未通过", detail=" | ".join(last_ret))

    def _sign(self, token: str, stamp: str, data: str) -> str:
        raw = f"{token}&{stamp}&{self.settings.app_key}&{data}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _raise_for_ret(self, ret: list[str]) -> None:
        joined = " ".join(ret)
        if any(hint in joined for hint in _RISK_HINTS):
            raise RiskControlError(
                "HTTP 路径命中淘宝风控（RGV587），无法直连 mtop 接口",
                detail=joined[:200],
            )
        if any(hint in joined for hint in _AUTH_HINTS):
            raise AuthRequiredError("登录态无效或已过期，请重新执行 login", detail=joined[:200])
        raise ParseError("mtop 接口返回失败", detail=joined[:200])


__all__ = ["CANDIDATES", "MtopHttpFetcher"]
