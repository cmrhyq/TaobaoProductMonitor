"""运行配置。

全部配置项都可以用环境变量覆盖，前缀 `TB_`，例如：

    TB_HEADLESS=false
    TB_STORAGE_STATE=taobao_storage_state.json
    TB_PROXY=http://127.0.0.1:7890
"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 实测有效的移动端 UA：淘宝 H5 接口对 UA 与终端类型敏感
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class Settings(BaseSettings):
    """全局配置（不可变语义：只读使用）。"""

    model_config = SettingsConfigDict(
        env_prefix="TB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 登录态 ----------
    storage_state: Path = Path("taobao_storage_state.json")
    #: 登录态超过该天数就提示（淘宝 cookie 通常 30~60 天失效）
    state_stale_days: int = 20

    # ---------- 浏览器 ----------
    headless: bool = True
    nav_timeout_ms: int = 45_000
    eval_timeout_ms: int = 15_000
    login_timeout_s: int = 300

    # ---------- HTTP ----------
    http_timeout_s: float = 15.0
    app_key: str = "12574478"
    mobile_ua: str = MOBILE_UA
    desktop_ua: str = DESKTOP_UA

    # ---------- 稳定性 ----------
    #: 单个策略的最大尝试次数（含首次）
    max_attempts: int = 3
    #: 指数退避基数（秒）
    backoff_base_s: float = 1.5
    #: 同一域名两次请求的最小间隔（秒），防止触发限流
    min_interval_s: float = 1.5

    # ---------- 其它 ----------
    proxy: str | None = None
    log_level: str = "INFO"

    @field_validator("proxy", mode="before")
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        """`TB_PROXY=` 这种留空的写法等价于不配置。

        否则空字符串会一路传到 httpx（proxy="" 直接抛 ValueError），
        把整个抓取链路拖垮——这是运维最容易写出的配置。
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def proxy_arg(self) -> dict[str, str] | None:
        """给 httpx / playwright 用的代理参数。"""
        if not self.proxy:
            return None
        return {"http://": self.proxy, "https://": self.proxy}

    def playwright_proxy(self) -> dict[str, str] | None:
        """给 playwright 用的代理参数。"""
        return {"server": self.proxy} if self.proxy else None


__all__ = ["DESKTOP_UA", "MOBILE_UA", "Settings"]
