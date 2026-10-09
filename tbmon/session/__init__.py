"""登录会话：登录态体检、浏览器会话、扫码登录。

    from tbmon.session import BrowserSession, login, validate_state

分层：
- `state.py`    登录态文件（storage_state）的读写与体检，不依赖 playwright
- `session.py`  BrowserSession：playwright 生命周期与上下文构造
- `login.py`    扫码登录交互流程
"""

from __future__ import annotations

from .login import LOGIN_URL, EventCallback, login
from .session import BrowserSession
from .state import (
    DOMAIN_KEYWORDS,
    LOGIN_COOKIE_NAMES,
    load_cookies,
    require_state,
    validate_state,
)

__all__ = [
    "BrowserSession",
    "DOMAIN_KEYWORDS",
    "EventCallback",
    "LOGIN_COOKIE_NAMES",
    "LOGIN_URL",
    "load_cookies",
    "login",
    "require_state",
    "validate_state",
]
