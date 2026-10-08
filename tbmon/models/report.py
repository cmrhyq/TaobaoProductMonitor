"""抓取过程的记录模型。

与 `product.py` 的区别：这里描述的是「这次抓取发生了什么」（耗时、尝试、告警、
登录态状态），而不是「商品本身长什么样」。两者生命周期不同，故分模块存放。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .product import ProductInfo


class AttemptRecord(BaseModel):
    """一次抓取尝试的留痕，用于排障。

    `strategy` 取值为策略注册表中的键（见 `tbmon.fetchers.registry`）。
    """

    strategy: str
    ok: bool
    elapsed_ms: int
    error: str | None = None


class FetchReport(BaseModel):
    """一次 fetch 调用的完整结果。"""

    ok: bool
    item_id: str | None = None
    product: ProductInfo | None = None
    attempts: list[AttemptRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: int = 0
    raw_path: str | None = None

    def to_json_obj(self) -> dict[str, Any]:
        """转成 JSON 可序列化的字典（CLI `--json` 使用）。"""
        return self.model_dump(mode="json")


class StateStatus(BaseModel):
    """登录态体检结果。"""

    exists: bool
    ok: bool
    reason: str
    cookie_count: int = 0
    age_days: float | None = None
    expires_in_days: float | None = None
    has_login_cookie: bool = False


__all__ = ["AttemptRecord", "FetchReport", "StateStatus"]
