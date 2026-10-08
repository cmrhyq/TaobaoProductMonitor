"""编排层测试：策略降级、重试语义、失败汇总（全程不联网、不开浏览器）。"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from tbmon.config import Settings
from tbmon.errors import AllStrategiesFailed, AuthRequiredError, RiskControlError, TransportError
from tbmon.fetchers import FetchOutcome
from tbmon.service import ItemService

FIXTURES = Path(__file__).parent / "fixtures"
ITEM_ID = "1050906790941"
PAYLOAD = json.loads((FIXTURES / "detail_mtop.json").read_text(encoding="utf-8"))


class FakeFetcher:
    """可编程的假策略：按需成功或抛出指定异常。"""

    def __init__(self, *, payload: dict | None = None, error: Exception | None = None,
                 source: str = "mtop-http") -> None:
        self.payload = payload if payload is not None else PAYLOAD
        self.error = error
        self.source = source
        self.calls = 0

    def fetch(self, item_id: str) -> FetchOutcome:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return FetchOutcome(payload=self.payload, source=self.source)


def make_settings(tmp_path: Path, **overrides) -> Settings:
    base = {
        "storage_state": tmp_path / "state.json",
        "max_attempts": 1,
        "backoff_base_s": 0.0,
        "min_interval_s": 0.0,
    }
    base.update(overrides)
    return Settings(**base)


def install_fakes(monkeypatch: pytest.MonkeyPatch, fakes: dict[str, FakeFetcher]) -> None:
    original = ItemService._build_fetcher

    def fake_build(self: ItemService, strategy: str):
        if strategy in fakes:
            return fakes[strategy]
        return original(self, strategy)

    monkeypatch.setattr(ItemService, "_build_fetcher", fake_build)


# ------------------------------------------------------------------ 正常路径
def test_browser_is_the_first_strategy(tmp_path, monkeypatch) -> None:
    fakes = {"browser": FakeFetcher(source="ssr-pc"), "http": FakeFetcher()}
    install_fakes(monkeypatch, fakes)

    with ItemService(make_settings(tmp_path)) as service:
        report = service.fetch(ITEM_ID)
        assert service._session is None  # 没走到 http，也就没开浏览器

    assert report.ok
    assert report.product is not None
    assert report.product.price.current == Decimal("522.00")  # 来自 detail_mtop.json 仿真 fixture
    assert report.product.source == "ssr-pc"
    assert fakes["browser"].calls == 1
    assert fakes["http"].calls == 0
    assert [a.strategy for a in report.attempts] == ["browser"]


# ------------------------------------------------------------------ 降级路径
def test_falls_back_to_http_after_risk_control(tmp_path, monkeypatch) -> None:
    fakes = {
        "browser": FakeFetcher(error=RiskControlError("RGV587 风控")),
        "http": FakeFetcher(),
    }
    install_fakes(monkeypatch, fakes)

    with ItemService(make_settings(tmp_path)) as service:
        report = service.fetch(ITEM_ID)

    assert report.ok
    assert report.product.source == "mtop-http"
    assert [(a.strategy, a.ok) for a in report.attempts] == [("browser", False), ("http", True)]


def test_risk_control_is_not_retried_in_place(tmp_path, monkeypatch) -> None:
    """风控不可重试：原地重试只会加重封禁，必须直接换策略。"""
    fakes = {"browser": FakeFetcher(error=RiskControlError("RGV587")), "http": FakeFetcher()}
    install_fakes(monkeypatch, fakes)

    with ItemService(make_settings(tmp_path, max_attempts=3)) as service:
        service.fetch(ITEM_ID)

    assert fakes["browser"].calls == 1


def test_transport_error_is_retried(tmp_path, monkeypatch) -> None:
    fakes = {"http": FakeFetcher(error=TransportError("连接超时"))}
    install_fakes(monkeypatch, fakes)

    with ItemService(make_settings(tmp_path, max_attempts=2)) as service:
        with pytest.raises(AllStrategiesFailed):
            service.fetch(ITEM_ID)

    assert fakes["http"].calls == 2


def test_browser_skipped_when_not_logged_in(tmp_path, monkeypatch) -> None:
    fakes = {"http": FakeFetcher(error=RiskControlError("RGV587"))}
    install_fakes(monkeypatch, fakes)

    with ItemService(make_settings(tmp_path)) as service:
        with pytest.raises(AllStrategiesFailed) as excinfo:
            service.fetch(ITEM_ID)
        # 登录态缺失时必须快速失败，不能白开一个浏览器
        assert service._session is None

    assert "browser" in str(excinfo.value)


def test_all_strategies_failed_reports_every_attempt(tmp_path, monkeypatch) -> None:
    fakes = {
        "http": FakeFetcher(error=RiskControlError("RGV587")),
        "browser": FakeFetcher(error=AuthRequiredError("登录态失效")),
    }
    install_fakes(monkeypatch, fakes)

    with ItemService(make_settings(tmp_path)) as service:
        with pytest.raises(AllStrategiesFailed) as excinfo:
            service.fetch(ITEM_ID)

    assert len(excinfo.value.attempts) == 2
    assert any("RGV587" in a for a in excinfo.value.attempts)


# ------------------------------------------------------------------ 其它行为
def test_strategy_order_is_canonical(tmp_path, monkeypatch) -> None:
    """调用方传入顺序不影响执行顺序：浏览器优先（实测 HTTP 直连必被风控）。"""
    fakes = {"http": FakeFetcher(), "browser": FakeFetcher(source="ssr-pc")}
    install_fakes(monkeypatch, fakes)

    with ItemService(make_settings(tmp_path)) as service:
        report = service.fetch(ITEM_ID, strategies=["http", "browser"])

    assert report.product.source == "ssr-pc"
    assert fakes["http"].calls == 0


def test_unknown_strategy_rejected(tmp_path) -> None:
    with ItemService(make_settings(tmp_path)) as service:
        with pytest.raises(ValueError):
            service.fetch(ITEM_ID, strategies=["curl"])


def test_save_raw_dumps_payload(tmp_path, monkeypatch) -> None:
    install_fakes(monkeypatch, {"http": FakeFetcher()})

    with ItemService(make_settings(tmp_path)) as service:
        report = service.fetch(ITEM_ID, save_raw=tmp_path / "raw")

    assert report.raw_path is not None
    assert json.loads(Path(report.raw_path).read_text(encoding="utf-8"))["data"]["item"]["itemId"] == ITEM_ID


def test_dom_source_adds_warning(tmp_path, monkeypatch) -> None:
    dom_payload = {
        "title": "MUJI 无印良品 靠垫",
        "price_candidates": [{"text": "¥522", "score": 9.0}],
    }
    install_fakes(monkeypatch, {"http": FakeFetcher(payload=dom_payload, source="dom-page")})

    with ItemService(make_settings(tmp_path)) as service:
        report = service.fetch(ITEM_ID)

    assert report.ok
    assert any("DOM" in w for w in report.warnings)
