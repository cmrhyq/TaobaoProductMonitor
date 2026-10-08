"""Web API 契约测试。

只验证端点的返回结构与守卫逻辑；不启动真实抓取、不打开浏览器、不发送邮件。

注：TestClient 不进入 `with` 上下文，因此 lifespan 不执行——
不会初始化数据库、也不会启动内嵌调度器。
"""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

import api.routes.monitor as monitor_route
import api.routes.session as session_route
from api.app import app

STATUS_KEYS = {
    "running", "trigger", "started_at", "finished_at",
    "total", "success", "failed", "skipped_reason", "last_error",
}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# --------------------------------------------------------------------- 健康与登录态
def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_session_state_shape(client: TestClient) -> None:
    response = client.get("/session/state")
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload["ok"], bool)
    assert isinstance(payload["reason"], str) and payload["reason"]
    assert isinstance(payload["cookie_count"], int)
    # 登录态路径必须归一为项目根下的绝对路径，不受进程 CWD 影响
    assert payload["storage_state"].endswith("taobao_storage_state.json")


def test_session_login_conflicts_with_running_cycle(client: TestClient, monkeypatch) -> None:
    """监控轮次在跑时不能同时开第二个浏览器，直接 409。"""
    monkeypatch.setattr(session_route, "is_running", lambda: True)
    response = client.post("/session/login", json={"timeout_s": 30})
    assert response.status_code == 409
    assert "正在执行" in response.json()["detail"]


def test_session_login_validates_timeout_range(client: TestClient) -> None:
    """非法 timeout 在进入浏览器之前就被拦下。"""
    assert client.post("/session/login", json={"timeout_s": 1}).status_code == 422
    assert client.post("/session/login", json={"timeout_s": 9999}).status_code == 422


# --------------------------------------------------------------------- 监控控制
def test_monitor_status_shape(client: TestClient) -> None:
    response = client.get("/monitor/status")
    assert response.status_code == 200

    payload = response.json()
    assert set(payload) == STATUS_KEYS
    assert isinstance(payload["running"], bool)
    assert isinstance(payload["total"], int)


def test_monitor_schedule_shape(client: TestClient) -> None:
    response = client.get("/monitor/schedule")
    assert response.status_code == 200

    payload = response.json()
    assert payload["enabled"] is True
    assert payload["interval_minutes"] >= 1
    assert isinstance(payload["run_on_startup"], bool)
    # 未走 lifespan，调度器未启动
    assert payload["running"] is False
    assert payload["next_run_at"] is None


def test_trigger_runs_cycle_in_background(client: TestClient, monkeypatch) -> None:
    called = threading.Event()
    triggers: list[str] = []

    def fake_task(**kwargs) -> dict:
        triggers.append(kwargs.get("trigger", ""))
        called.set()
        return {"total": 0, "success": 0, "failed": 0, "skipped": "fake"}

    monkeypatch.setattr(monitor_route, "product_monitor_task", fake_task)
    monkeypatch.setattr(monitor_route, "is_running", lambda: False)

    response = client.post("/monitor/trigger")
    assert response.status_code == 200
    assert response.json()["status"] == "running"

    assert called.wait(timeout=3) is True
    assert triggers == ["manual"]


def test_trigger_conflicts_when_cycle_running(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(monitor_route, "is_running", lambda: True)
    response = client.post("/monitor/trigger")
    assert response.status_code == 409


# --------------------------------------------------------------------- 商品
def test_list_products_returns_list(client: TestClient) -> None:
    response = client.get("/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_missing_product_returns_404(client: TestClient) -> None:
    assert client.get("/products/999999").status_code == 404
    assert client.get("/products/999999/snapshot").status_code == 404
    assert client.get("/products/999999/history").status_code == 404


def test_create_product_requires_notify_email(client: TestClient) -> None:
    response = client.post("/products", json={"product_url": "https://x", "product_name": "y"})
    assert response.status_code == 422


def test_create_product_rejects_unparsable_share_text(client: TestClient) -> None:
    """淘口令目前不支持，应给出 4xx 而不是 500。"""
    response = client.post(
        "/products", json={"share_text": "￥CZ028abcdef￥", "notify_email": "a@b.com"}
    )
    assert response.status_code == 400
    assert "parse" in response.json()["detail"].lower()
