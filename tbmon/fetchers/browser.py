"""浏览器真实指纹路径（主力策略）。

实网探测结论（2026-10）决定了这里的设计：

1. H5 详情页（`h5.m.taobao.com/awp/core/detail.htm`）即使用真实浏览器 + 有效登录态，
   其 `mtop.taobao.detail.data.get` 也会返回 `RGV587_ERROR` 并跳转 `punish` 拒绝页
   （页面显示"亲，访问被拒绝"），即整条 H5 链路已被风控封死。
2. **PC 详情页完全正常**：`item.taobao.com/item.htm?id=` 会自动跳到对应站点
   （淘宝 / 天猫 / 天猫国际），页面渲染出真实价格，且页面自身的接口调用全部 SUCCESS。
3. PC 页把整份商品数据以 SSR 形式注入到 `window.__ICE_APP_CONTEXT__`
   的 `loaderData.home.data.res`，其结构与标准详情接口**一致**
   （`item` / `seller` / `skuBase` / `skuCore` / `componentsVO`），可直接复用解析层。
4. 在 PC 页里用 `lib.mtop` 反调 H5 详情接口会被拒（`UNEXCEPT_REQUEST::错误的请求类型`），
   所以不做无意义的补发请求。

因此浏览器策略 = PC 页 + 三级降级：SSR 内嵌数据 → 被动截获页面自身接口 → DOM 提取。
注入的 JS 见 `scripts.py`。
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import Settings
from ..errors import AuthRequiredError, ParseError, RiskControlError
from ..session import BrowserSession
from .base import FetchOutcome, decode_jsonp
from .scripts import EXTRACT_DOM_JS, PAGE_TEXT_JS, READ_SSR_JS, SSR_PATH, SSR_READY_JS

log = logging.getLogger(__name__)

#: 商品详情页地址（会自动跳转到淘宝 / 天猫 / 天猫国际对应站点）
DETAIL_URL = "https://item.taobao.com/item.htm?id={item_id}"
#: 被动截获时的候选接口关键字（页面自己的详情 / 容器接口）
_CAPTURE_HINTS = ("detail", "containerfacade")
#: 截获到的 data 里必须含这些价格字段之一，否则可能是无关的小接口
_PRICE_KEYS = ("priceText", "priceMoney", "sku2info", "subPrice")
#: 页面正文命中这些关键字 = 被风控拒绝
_RISK_HINTS = ("RGV587", "USER_VALIDATE", "被挤爆", "访问被拒绝", "FAIL_SYS_TRAFFIC_LIMIT")
#: URL 命中这些关键字 = 被风控拒绝（punish 拒绝页 / 滑块验证）
_RISK_URL_HINTS = ("punish", "x5secdata", "_____tmd_____")
#: URL 命中这些关键字 = 被重定向到登录页
_LOGIN_URL_HINTS = ("login.", "havanaone/login")
#: 等待页面稳定的额外时长（SSR 就绪后仍有少量异步渲染）
_SETTLE_MS = 500
#: DOM 兜底前额外等待，给异步渲染留时间
_DOM_SETTLE_MS = 800


class BrowserDetailFetcher:
    """基于已登录 PC 详情页抓取商品信息。"""

    name = "browser"

    def __init__(self, session: BrowserSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    # ------------------------------------------------------------------ 对外
    def fetch(self, item_id: str) -> FetchOutcome:
        """抓取商品详情，按 SSR → 接口截获 → DOM 的顺序降级。"""
        page = self.session.new_page()
        captured: dict[str, Any] = {}
        page.on("response", lambda resp: self._capture(resp, captured))
        try:
            self._open(page, item_id)
            self._guard(page)

            if outcome := self._from_ssr(page):
                return outcome

            if captured.get("payload"):
                log.info("SSR 数据缺失，改用被动截获的接口响应：%s", captured.get("api"))
                return FetchOutcome(
                    payload=captured["payload"],
                    source="mtop-page",
                    meta={"api": captured.get("api", ""), "mode": "passive-capture"},
                )

            log.info("SSR 与接口均无数据，降级 DOM 提取")
            return FetchOutcome(
                payload=self._dom_extract(page), source="dom-page", meta={"mode": "dom"}
            )
        finally:
            try:
                page.close()
            except Exception:  # pragma: no cover
                pass
            # 浏览器会自动续期 cookie，顺手回写，延长登录态寿命
            if self.session.is_logged_in():
                try:
                    self.session.save_storage_state()
                except Exception as exc:  # pragma: no cover
                    log.warning("登录态回写失败：%s", exc)

    # ------------------------------------------------------------------ 内部
    @staticmethod
    def _capture(response: Any, sink: dict[str, Any]) -> None:
        """被动收集页面自身发出的接口响应 —— 免费的第二路数据源。

        注意：playwright 的事件回调里抛异常会冒泡污染整个调用流程，
        因此这里必须吞掉所有异常（回调只做"有就存下来"）。
        """
        try:
            url = response.url
            if not any(hint in url for hint in _CAPTURE_HINTS) or "mtop" not in url:
                return
            body = decode_jsonp(response.text())
            if not isinstance(body, dict) or not body.get("data"):
                return
            ret = body.get("ret") or []
            if not any(str(r).startswith("SUCCESS") for r in ret):
                return
            data = body["data"]
            # 只留"带价格信息且更大"的那份，避免被页面上的小接口覆盖
            if not any(key in str(data) for key in _PRICE_KEYS):
                return
            size = len(str(data))
            if size < sink.get("size", 0):
                return
            sink.update(payload=data, api=str(body.get("api", "")), size=size)
        except Exception:  # noqa: BLE001 - 回调必须绝对安全
            return

    def _open(self, page: Any, item_id: str) -> None:
        """打开详情页并等待 SSR 数据就绪（超时不抛错，交给降级流程）。"""
        try:
            page.goto(DETAIL_URL.format(item_id=item_id), wait_until="domcontentloaded")
        except Exception as exc:
            log.warning("详情页加载未完成（%s），继续解析当前内容", exc.__class__.__name__)
        try:
            page.wait_for_function(SSR_READY_JS, timeout=self.settings.eval_timeout_ms)
        except Exception:
            log.info("等待 SSR 数据超时，进入降级流程")
        page.wait_for_timeout(_SETTLE_MS)

    def _guard(self, page: Any) -> None:
        """到站即查：落到登录页 / 风控页时立刻给出可执行的恢复建议。"""
        url = page.url or ""
        if any(k in url for k in _LOGIN_URL_HINTS):
            raise AuthRequiredError(
                "详情页被重定向到登录页，登录态已失效；请重新执行：python -m tbmon login",
                detail=url[:160],
            )
        if any(k in url for k in _RISK_URL_HINTS):
            raise RiskControlError(
                "详情页被判定为风控访问（punish 拒绝页）；建议更换网络出口或降低抓取频率",
                detail=url[:160],
            )

    def _from_ssr(self, page: Any) -> FetchOutcome | None:
        """首选路径：读 PC 页 SSR 注入的完整商品数据。"""
        try:
            payload = page.evaluate(READ_SSR_JS)
        except Exception as exc:
            log.warning("读取 SSR 数据异常：%s", exc)
            return None

        if not payload:
            self._raise_if_denied(self._page_text(page))
            return None
        res = payload.get("res") if isinstance(payload, dict) else None
        if not isinstance(res, dict) or not res:
            return None
        return FetchOutcome(
            payload=res,
            source="ssr-pc",
            meta={"mode": "ssr", "keys": payload.get("keys", []), "path": SSR_PATH},
        )

    def _page_text(self, page: Any) -> str:
        try:
            return page.evaluate(PAGE_TEXT_JS)[:2000]
        except Exception:
            return ""

    def _raise_if_denied(self, text: str) -> None:
        if any(hint in text for hint in _RISK_HINTS):
            raise RiskControlError("页面正文提示访问被拒绝（风控），请更换网络出口或降低频率")

    def _dom_extract(self, page: Any) -> dict[str, Any]:
        """兜底路径：从渲染后的 DOM 里提取（字段完整度最低）。"""
        page.wait_for_timeout(_DOM_SETTLE_MS)
        try:
            dom = page.evaluate(EXTRACT_DOM_JS)
        except Exception as exc:
            raise ParseError(f"DOM 提取失败：{exc}") from exc
        if isinstance(dom, dict) and not dom.get("price_text") and not dom.get("title"):
            raise ParseError("DOM 中未找到价格与标题（可能未登录或页面结构已变）")
        return dom if isinstance(dom, dict) else {}


__all__ = ["BrowserDetailFetcher", "DETAIL_URL"]
