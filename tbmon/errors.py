"""统一异常体系。

设计要点：把"失败语义"和"重试决策"解耦。
上层（service）只需要看 `resolved` / `retryable` 两个属性，不需要写 if-else 判断错误码。
"""

from __future__ import annotations

from collections.abc import Sequence


class TbMonError(Exception):
    """本程序所有异常的基类。"""

    #: 是否值得原地重试（网络抖动、风控限流等）
    retryable: bool = False
    #: 是否属于"必须人工介入"（如重新登录）
    needs_human: bool = False

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - 便于日志
        return f"{self.message} ({self.detail})" if self.detail else self.message


class LinkResolveError(TbMonError):
    """分享链接 / 商品 ID 无法解析。"""


class AuthRequiredError(TbMonError):
    """未登录或登录态失效，需要重新执行 login。"""

    needs_human = True


class RiskControlError(TbMonError):
    """命中淘宝风控（RGV587 / 被挤爆 / 滑块验证）。

    刻意设为不可重试：原地重试既不会让风控消失，还可能加重封禁。
    正确的恢复路径是**切换策略**（HTTP → 浏览器真实指纹），由 service 负责。
    """

    retryable = False


class TransportError(TbMonError):
    """网络层失败：超时、连接重置、5xx。"""

    retryable = True


class ParseError(TbMonError):
    """拿到了响应，但无法解析出有效商品信息。"""


class AllStrategiesFailed(TbMonError):
    """所有抓取策略都失败，附带每次尝试的摘要。"""

    def __init__(self, message: str, *, attempts: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.attempts = list(attempts)

    def __str__(self) -> str:  # pragma: no cover - 便于日志
        if not self.attempts:
            return self.message
        lines = "\n".join(f"  - {a}" for a in self.attempts)
        return f"{self.message}\n{lines}"


__all__ = [
    "AllStrategiesFailed",
    "AuthRequiredError",
    "LinkResolveError",
    "ParseError",
    "RiskControlError",
    "TbMonError",
    "TransportError",
]
