"""登录态体检测试。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from tbmon.session import load_cookies, validate_state

ITEM_DOMAIN = ".taobao.com"


def make_cookie(name: str, value: str = "v", *, expires: float | None = None,
                domain: str = ITEM_DOMAIN) -> dict:
    return {
        "name": name,
        "value": value,
        "domain": domain,
        "path": "/",
        "expires": time.time() + 86400 * 30 if expires is None else expires,
        "httpOnly": False,
        "secure": True,
        "sameSite": "None",
    }


def write_state(path: Path, cookies: list[dict]) -> Path:
    path.write_text(json.dumps({"cookies": cookies, "origins": []}), encoding="utf-8")
    return path


def test_missing_state(tmp_path: Path) -> None:
    status = validate_state(tmp_path / "nope.json")
    assert not status.exists and not status.ok
    assert "login" in status.reason


def test_valid_state(tmp_path: Path) -> None:
    path = write_state(tmp_path / "state.json", [make_cookie("unb", "12345"), make_cookie("cookie2", "x")])
    status = validate_state(path)
    assert status.ok and status.has_login_cookie
    assert status.cookie_count == 2
    assert status.reason == "登录态有效"


def test_state_without_login_cookie(tmp_path: Path) -> None:
    path = write_state(tmp_path / "state.json", [make_cookie("cna", "abc")])
    status = validate_state(path)
    assert not status.ok
    assert "登录 cookie" in status.reason


def test_expired_login_cookie(tmp_path: Path) -> None:
    path = write_state(
        tmp_path / "state.json",
        [make_cookie("unb", "12345", expires=time.time() - 3600), make_cookie("cookie2", "x", expires=time.time() - 60)],
    )
    status = validate_state(path)
    assert not status.ok
    assert "过期" in status.reason
    assert status.expires_in_days == 0.0


def test_corrupted_state(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{ not json", encoding="utf-8")
    status = validate_state(path)
    assert not status.ok
    assert "损坏" in status.reason


def test_load_cookies_filters_non_taobao_domains(tmp_path: Path) -> None:
    path = write_state(
        tmp_path / "state.json",
        [
            make_cookie("unb", "12345"),
            make_cookie("cookie2", "c2", domain=".tmall.com"),
            make_cookie("session", "sess", domain=".example.com"),
            make_cookie("empty", "", domain=".taobao.com"),
        ],
    )
    cookies = load_cookies(path)
    assert cookies == {"unb": "12345", "cookie2": "c2"}
