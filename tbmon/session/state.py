"""登录态（Playwright `storage_state`）的读写与体检。

设计要点：登录态是**显式体检**的 —— 抓取前先看 cookie 是否还在、是否过期，
发现失效立即抛 `AuthRequiredError` 并给出可执行提示，而不是打开浏览器撞登录页。
本模块不导入 playwright，纯文件与数据判断，可完全离线测试。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..config import Settings
from ..errors import AuthRequiredError
from ..models import StateStatus

#: 淘宝登录后才会有这些 cookie
LOGIN_COOKIE_NAMES = ("unb", "_nk_", "cookie17", "tracknick")
#: 只保留这些域下的 cookie（storage_state 里还混着其它站点的）
DOMAIN_KEYWORDS = ("taobao.com", "tmall.com", "alicdn.com", "taobao.hk")
#: 判断剩余有效期时优先看这几个长期 cookie
_EXPIRY_COOKIE_NAMES = ("unb", "cookie2")


def _read_state(path: Path) -> dict:
    """读取 storage_state 文件；不存在或损坏一律返回空字典。"""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_cookies(path: Path | str) -> dict[str, str]:
    """从 storage_state 里取出淘宝域 cookie（HTTP 快速路径复用登录态）。"""
    state = _read_state(Path(path))
    cookies: dict[str, str] = {}
    for cookie in state.get("cookies", []):
        domain = cookie.get("domain", "")
        if any(key in domain for key in DOMAIN_KEYWORDS) and cookie.get("value"):
            cookies[cookie["name"]] = cookie["value"]
    return cookies


def validate_state(path: Path | str, *, stale_days: int = 20) -> StateStatus:
    """体检登录态：存在性 / 登录 cookie / 过期时间。"""
    path = Path(path)
    if not path.exists():
        return StateStatus(exists=False, ok=False, reason=f"登录态文件不存在：{path}（请执行 login）")

    state = _read_state(path)
    cookies = state.get("cookies", [])
    if not cookies:
        return StateStatus(exists=True, ok=False, reason="登录态文件为空或损坏")

    names = {c.get("name") for c in cookies if c.get("value")}
    has_login_cookie = bool(names & set(LOGIN_COOKIE_NAMES))

    age_days = (time.time() - path.stat().st_mtime) / 86400

    # 关键登录 cookie 的剩余有效期
    expires_in_days: float | None = None
    for cookie in cookies:
        if cookie.get("name") in _EXPIRY_COOKIE_NAMES and cookie.get("expires", -1) > 0:
            left = (cookie["expires"] - time.time()) / 86400
            expires_in_days = left if expires_in_days is None else min(expires_in_days, left)

    if not has_login_cookie:
        return StateStatus(
            exists=True, ok=False, reason="未检测到登录 cookie，登录态已失效",
            cookie_count=len(cookies), age_days=round(age_days, 1), expires_in_days=None,
            has_login_cookie=False,
        )

    if expires_in_days is not None and expires_in_days <= 0:
        return StateStatus(
            exists=True, ok=False, reason="登录 cookie 已过期",
            cookie_count=len(cookies), age_days=round(age_days, 1), expires_in_days=0.0,
            has_login_cookie=True,
        )

    reason = "登录态有效"
    if age_days > stale_days:
        reason = f"登录态有效但已保存 {age_days:.0f} 天（建议重新登录）"
    elif expires_in_days is not None and expires_in_days < 3:
        reason = f"登录态将在 {expires_in_days:.1f} 天后过期"

    return StateStatus(
        exists=True, ok=True, reason=reason, cookie_count=len(cookies),
        age_days=round(age_days, 1),
        expires_in_days=None if expires_in_days is None else round(expires_in_days, 1),
        has_login_cookie=True,
    )


def require_state(settings: Settings) -> StateStatus:
    """抓取前置检查：不通过直接抛 `AuthRequiredError`。"""
    status = validate_state(settings.storage_state, stale_days=settings.state_stale_days)
    if not status.ok:
        raise AuthRequiredError(
            f"{status.reason}；请先执行：python -m tbmon login",
            detail=str(settings.storage_state),
        )
    return status


__all__ = [
    "DOMAIN_KEYWORDS",
    "LOGIN_COOKIE_NAMES",
    "load_cookies",
    "require_state",
    "validate_state",
]
