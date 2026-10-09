"""TaobaoMonitor 业务编排测试（全离线）。

注入假的 ItemService 与假仓储，不碰网络、不碰数据库、不启动浏览器。
覆盖：抓取成功→落价→落快照→规则判定，以及各类失败路径。

这是「抓取后端换成 tbmon」之后，业务层唯一需要保证的契约。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

import service.monitor as monitor_module
from data.models import Product
from data.repository.product_repo import (
    MONITOR_STATUS_ENDED,
    MONITOR_STATUS_MONITORING,
    MONITOR_STATUS_NOT_STARTED,
)
from service.monitor import TaobaoMonitor
from tbmon.errors import AllStrategiesFailed, AuthRequiredError, TbMonError
from tbmon.models import FetchReport, Money, ProductInfo, ShopInfo, SkuInfo, StateStatus

ITEM_ID = "1050906790941"
PRODUCT_URL = "https://e.tb.cn/h.jZFrbZq1TUvRKLb?tk=0ePNTqqrdlY"


# --------------------------------------------------------------------- 测试替身
class FakeSettings:
    class mail:
        host = "smtp.test"
        sender = "sender@test.com"
        license_key = "license"


class FakeItemService:
    """只实现 TaobaoMonitor 用到的三个方法。"""

    def __init__(self, product: ProductInfo | None = None, error: Exception | None = None,
                 login_ok: bool = True) -> None:
        self._product = product
        self._error = error
        self._login_ok = login_ok
        self.calls: list[str] = []
        self.closed = False

    def fetch(self, text: str, **kwargs) -> FetchReport:
        self.calls.append(text)
        if self._error is not None:
            raise self._error
        assert self._product is not None
        return FetchReport(ok=True, item_id=self._product.item_id, product=self._product, elapsed_ms=12)

    def login_state(self) -> StateStatus:
        return StateStatus(exists=True, ok=self._login_ok, reason="ok" if self._login_ok else "登录态已失效")

    def close(self) -> None:
        self.closed = True


class FakeProductRepo:
    def __init__(self) -> None:
        self.fail_count = 0
        self.item_id: str | None = None
        self.price_updates: list[dict] = []
        self.status_updates: list[int] = []

    def increment_fail_count(self, product_id: int) -> bool:
        self.fail_count += 1
        return True

    def update_item_id(self, product_id: int, item_id: str) -> bool:
        self.item_id = item_id
        return True

    def update_product_prices(self, product_id: int, current_price: float,
                              initial_price: float | None = None,
                              lowest_price: float | None = None) -> bool:
        self.price_updates.append(
            {"current": current_price, "initial": initial_price, "lowest": lowest_price}
        )
        return True

    def update_product_status(self, product_id: int, status: int) -> bool:
        self.status_updates.append(status)
        return True


class FakePriceRepo:
    def __init__(self, initial: Decimal | None = Decimal("500.00"),
                 lowest: Decimal | None = Decimal("382.00")) -> None:
        self.inserted: list[dict] = []
        self._initial = initial
        self._lowest = lowest

    def insert_price(self, product_id: int, price: Decimal, fetch_method: str = "api",
                     original_price: Decimal | None = None) -> int:
        self.inserted.append(
            {"price": price, "fetch_method": fetch_method, "original_price": original_price}
        )
        return len(self.inserted)

    def query_first_price(self, product_id: int) -> Decimal | None:
        return self._initial

    def query_lowest_price(self, product_id: int) -> Decimal | None:
        return self._lowest


class FakeRuleRepo:
    def __init__(self, rules: list[dict] | None = None) -> None:
        self._rules = rules if rules is not None else []
        self.inserted: list[tuple] = []

    def get_active_rules(self, product_id: int) -> list[dict]:
        return self._rules

    def insert_rule(self, product_id: int, rule_type: str, **kwargs) -> int:
        self.inserted.append((product_id, rule_type, kwargs))
        return 1


class FakeNotificationRepo:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def insert_notification(self, **kwargs) -> int:
        self.rows.append(kwargs)
        return len(self.rows)


class FakeSnapshotRepo:
    def __init__(self, returns: int | None = 1) -> None:
        self.saved: list[tuple[int, ProductInfo]] = []
        self._returns = returns

    def insert_snapshot(self, product_id: int, product: ProductInfo, **kwargs) -> int | None:
        self.saved.append((product_id, product))
        return self._returns


class FakeEmailService:
    sent: list[object] = []

    def __init__(self, email_sender) -> None:
        self.email_sender = email_sender

    def send(self) -> bool:
        FakeEmailService.sent.append(self.email_sender)
        return True


# --------------------------------------------------------------------- 夹具
def _orm_product(status: int = MONITOR_STATUS_NOT_STARTED, item_id: str | None = None) -> Product:
    return Product(
        product_id=1,
        user_id=1,
        platform="淘宝",
        product_url=PRODUCT_URL,
        product_name="MUJI 无印良品 柔软清凉棉多用途靠垫",
        product_tk="0ePNTqqrdlY",
        item_id=item_id,
        monitor_status=status,
        notify_email="notify@test.com",
    )


def _product_info(price: Money | None = None, item_id: str = ITEM_ID) -> ProductInfo:
    return ProductInfo(
        item_id=item_id,
        url=f"https://item.taobao.com/item.htm?id={item_id}",
        title="MUJI 无印良品 柔软清凉棉多用途靠垫 55×40×20cm",
        price=price
        or Money(
            current=Decimal("382.00"),
            current_text="382起",
            original=Decimal("522.00"),
            low=Decimal("382.00"),
            high=Decimal("420.00"),
        ),
        skus=[SkuInfo(sku_id="1", props={"颜色": "象牙色"}, price=Decimal("382.00"), stock=5)],
        images=["https://img.alicdn.com/a.jpg"],
        shop=ShopInfo(shop_id="479456214", name="天猫国际全球探物"),
        attributes={"品牌": "MUJI/无印良品"},
        stock_total=17,
        sold_text="已售 4",
        source="ssr-pc",
        fetched_at=datetime(2026, 10, 8, 23, 30),
    )


def _build(fake_service: FakeItemService, **overrides):
    """组装被测对象 + 全部假仓储。"""
    repos = {
        "product_repo": overrides.get("product_repo") or FakeProductRepo(),
        "price_repo": overrides.get("price_repo") or FakePriceRepo(),
        "rule_repo": overrides.get("rule_repo") or FakeRuleRepo(),
        "notification_repo": overrides.get("notification_repo") or FakeNotificationRepo(),
        "snapshot_repo": overrides.get("snapshot_repo") or FakeSnapshotRepo(),
    }
    monitor = TaobaoMonitor(FakeSettings(), service=fake_service, **repos)
    return monitor, repos


@pytest.fixture(autouse=True)
def _offline_email(monkeypatch):
    """通知必测但绝不真发信。"""
    FakeEmailService.sent = []
    monkeypatch.setattr(monitor_module, "EmailService", FakeEmailService)


# --------------------------------------------------------------------- 正常路径
def test_first_monitor_records_price_snapshot_and_status() -> None:
    service = FakeItemService(product=_product_info())
    monitor, repos = _build(service)

    assert monitor.monitor_product(_orm_product(MONITOR_STATUS_NOT_STARTED)) is True

    # 抓取入参是 product_url（每次重新解析，天然兼容短链改版）
    assert service.calls == [PRODUCT_URL]

    # 价格落库：实付价 + 优惠前价 + 数据来源
    assert repos["price_repo"].inserted == [
        {"price": Decimal("382.00"), "fetch_method": "ssr-pc", "original_price": Decimal("522.00")}
    ]

    # 富数据落库
    assert len(repos["snapshot_repo"].saved) == 1
    assert repos["snapshot_repo"].saved[0][0] == 1
    assert repos["snapshot_repo"].saved[0][1].title.startswith("MUJI")

    # 首次监控：initial = lowest = current，随后进入「监控中」
    assert repos["product_repo"].price_updates[0]["current"] == 382.0
    assert repos["product_repo"].price_updates[0]["initial"] == 382.0
    assert repos["product_repo"].price_updates[0]["lowest"] == 382.0
    assert repos["product_repo"].status_updates == [MONITOR_STATUS_MONITORING]
    assert repos["notification_repo"].rows == []


def test_item_id_is_normalised_from_report() -> None:
    """存量 item_id 为空/过期时，用本次解析出的真实 ID 回写。"""
    service = FakeItemService(product=_product_info())
    monitor, repos = _build(service)
    product = _orm_product(item_id=None)

    monitor.monitor_product(product)

    assert repos["product_repo"].item_id == ITEM_ID
    assert product.item_id == ITEM_ID


def test_rule_triggered_sends_notification_and_ends_monitoring() -> None:
    """首次价 500 → 现价 382，默认规则（任意降价）应立即触发通知并结束监控。"""
    service = FakeItemService(product=_product_info())
    notification_repo = FakeNotificationRepo()
    monitor, repos = _build(service, notification_repo=notification_repo)

    assert monitor.monitor_product(_orm_product(MONITOR_STATUS_MONITORING)) is True

    assert len(FakeEmailService.sent) == 1
    assert "降价通知" in FakeEmailService.sent[0].email_theme
    assert len(notification_repo.rows) == 1
    assert notification_repo.rows[0]["notify_target"] == "notify@test.com"
    assert "382" in notification_repo.rows[0]["notify_content"]
    assert repos["product_repo"].status_updates == [MONITOR_STATUS_ENDED]


def test_no_drop_keeps_monitoring_without_notification() -> None:
    service = FakeItemService(product=_product_info(price=Money(current=Decimal("520.00"))))
    monitor, repos = _build(service)

    assert monitor.monitor_product(_orm_product(MONITOR_STATUS_MONITORING)) is True

    assert repos["notification_repo"].rows == []
    assert repos["product_repo"].status_updates == []


# --------------------------------------------------------------------- 失败路径
@pytest.mark.parametrize(
    "error",
    [
        AllStrategiesFailed("抓取失败：browser 打开详情页超时", attempts=["browser: timeout"]),
        AuthRequiredError("登录态已失效"),
        TbMonError("意料之外的抓取错误"),
    ],
)
def test_fetch_failure_counts_and_does_not_touch_price(error: Exception) -> None:
    service = FakeItemService(error=error)
    monitor, repos = _build(service)

    assert monitor.monitor_product(_orm_product()) is False

    assert repos["product_repo"].fail_count == 1
    assert repos["price_repo"].inserted == []
    assert repos["snapshot_repo"].saved == []
    assert repos["product_repo"].price_updates == []
    assert repos["notification_repo"].rows == []


def test_missing_price_is_a_failure() -> None:
    """完全取不到价格才算失败——不能拿 0 冒充。"""
    service = FakeItemService(product=_product_info(price=Money()))
    monitor, repos = _build(service)

    assert monitor.monitor_product(_orm_product()) is False

    assert repos["product_repo"].fail_count == 1
    assert repos["price_repo"].inserted == []


def test_range_price_falls_back_to_lowest() -> None:
    """多 SKU 区间价（无统一实付价）取最低价，否则这类商品会永久失败。"""
    service = FakeItemService(
        product=_product_info(price=Money(low=Decimal("382.00"), high=Decimal("420.00")))
    )
    monitor, repos = _build(service)

    assert monitor.monitor_product(_orm_product(MONITOR_STATUS_NOT_STARTED)) is True

    assert repos["price_repo"].inserted[0]["price"] == Decimal("382.00")
    assert repos["price_repo"].inserted[0]["original_price"] is None


def test_snapshot_failure_does_not_break_price_monitoring() -> None:
    """快照落库失败不应影响价格监控主流程。"""
    service = FakeItemService(product=_product_info())
    monitor, repos = _build(service, snapshot_repo=FakeSnapshotRepo(returns=None))

    assert monitor.monitor_product(_orm_product(MONITOR_STATUS_NOT_STARTED)) is True
    assert len(repos["price_repo"].inserted) == 1


# --------------------------------------------------------------------- 资源与解析
def test_context_manager_closes_service() -> None:
    service = FakeItemService(product=_product_info())
    with TaobaoMonitor(FakeSettings(), service=service) as monitor:
        assert monitor.login_state().ok is True

    assert service.closed is True


def test_close_is_idempotent_and_safe_without_service() -> None:
    monitor = TaobaoMonitor(FakeSettings(), service=FakeItemService())
    monitor.close()
    monitor.close()  # 重复关闭不应抛错

    # 未注入 service 时 close() 不应触发惰性创建
    untouched = TaobaoMonitor(FakeSettings(), service=None, product_repo=FakeProductRepo())
    untouched.close()
    assert untouched._service is None


def test_save_product_info_from_share_text() -> None:
    product_repo = FakeProductRepo()
    rule_repo = FakeRuleRepo()
    captured: dict = {}

    def fake_insert(**kwargs) -> int:
        captured.update(kwargs)
        return 7

    product_repo.insert_product = fake_insert  # type: ignore[method-assign]
    monitor = TaobaoMonitor(
        FakeSettings(), service=FakeItemService(), product_repo=product_repo, rule_repo=rule_repo
    )

    share_text = (
        "【淘宝】https://e.tb.cn/h.jZFrbZq1TUvRKLb?tk=0ePNTqqrdlY CZ028 "
        "「MUJI 无印良品 柔软清凉棉多用途靠垫 554020cm」"
    )
    assert monitor.save_product_info(share_text, "notify@test.com") == 7

    assert captured["platform"] == "淘宝"
    assert captured["product_name"].startswith("MUJI")
    assert captured["product_tk"] == "0ePNTqqrdlY"
    assert captured["product_url"].startswith("https://e.tb.cn/")
    assert captured["notify_email"] == "notify@test.com"
    assert rule_repo.inserted == [(7, "absolute_drop", {"threshold_value": 0.01})]


def test_save_product_info_tolerates_missing_title() -> None:
    """分享文本格式会变；缺标题不该让添加商品失败。"""
    captured: dict = {}

    def fake_insert(**kwargs) -> int:
        captured.update(kwargs)
        return 8

    product_repo = FakeProductRepo()
    product_repo.insert_product = fake_insert  # type: ignore[method-assign]
    monitor = TaobaoMonitor(FakeSettings(), service=FakeItemService(), product_repo=product_repo)

    assert monitor.save_product_info("https://e.tb.cn/h.abc?tk=xyz", "a@b.com") == 8
    assert captured["product_name"].startswith("淘宝商品")
    assert captured["platform"] == "淘宝"


def test_save_product_info_rejects_unusable_text() -> None:
    monitor = TaobaoMonitor(FakeSettings(), service=FakeItemService(), product_repo=FakeProductRepo())

    assert monitor.save_product_info("￥CZ028abcdef￥", "a@b.com") is None
    assert monitor.save_product_info("", "a@b.com") is None
