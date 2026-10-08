"""
Taobao product price monitor service.

业务编排层：抓取 → 价格落库 → 快照落库 → 规则判定 → 邮件通知。

抓取由 `tbmon.ItemService` 独家承担（旧的 H5 API / Playwright 降级实现已被淘宝风控
封死并删除）。本模块不关心请求细节与字段映射。

⚠️ 线程约束：`ItemService` 会缓存 Playwright 浏览器会话，而 Playwright 的同步对象
禁止跨线程使用。因此 TaobaoMonitor 必须在**同一个线程内创建、使用并关闭**，不要把
它做成进程级单例供多个请求共享；服务端每轮监控新建一个实例。
"""

from decimal import Decimal

import structlog

from config.settings import Settings, get_settings
from data.models import Product
from data.repository.notification_repo import NotificationRepository
from data.repository.price_repo import PriceRepository
from data.repository.product_repo import (
    MONITOR_STATUS_ENDED,
    MONITOR_STATUS_MONITORING,
    MONITOR_STATUS_NOT_STARTED,
    ProductRepository,
)
from data.repository.rule_repo import RuleRepository
from data.repository.snapshot_repo import SnapshotRepository
from tbmon import ItemService, TbMonError, parse_share_text
from tbmon.models import ProductInfo, StateStatus
from utils.email.send_email import EmailSender, EmailService
from utils.email.template import EmailTemplate

logger = structlog.get_logger(__name__)


class TaobaoMonitor:
    """
    Main monitoring service that orchestrates price checking,
    rule evaluation, and notifications.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        service: ItemService | None = None,
        product_repo: ProductRepository | None = None,
        price_repo: PriceRepository | None = None,
        rule_repo: RuleRepository | None = None,
        notification_repo: NotificationRepository | None = None,
        snapshot_repo: SnapshotRepository | None = None,
    ):
        """依赖全部可注入，便于离线单测；默认才构造真实实现。"""
        self._settings = settings or get_settings()
        self._service = service
        self._product_repo = product_repo or ProductRepository()
        self._price_repo = price_repo or PriceRepository()
        self._rule_repo = rule_repo or RuleRepository()
        self._notification_repo = notification_repo or NotificationRepository()
        self._snapshot_repo = snapshot_repo or SnapshotRepository()
        self._email_template = EmailTemplate()

    # ------------------------------------------------------------------ 生命周期
    @property
    def service(self) -> ItemService:
        """惰性创建抓取服务（不会启动浏览器）。"""
        if self._service is None:
            self._service = ItemService(self._settings.fetch)
        return self._service

    def close(self) -> None:
        """释放浏览器等资源；可重复调用。"""
        if self._service is not None:
            self._service.close()

    def __enter__(self) -> "TaobaoMonitor":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def login_state(self) -> StateStatus:
        """登录态体检，不启动浏览器。"""
        return self.service.login_state()

    # ------------------------------------------------------------------ 主流程
    def monitor_product(self, product: Product) -> bool:
        """
        Monitor a single product: fetch price, evaluate rules, send notifications.

        Returns:
            True if monitoring cycle completed successfully
        """
        log = logger.bind(product_id=product.product_id, product_name=product.product_name)
        log.info("Starting product monitor cycle")

        try:
            # 每次都以 product_url 为输入重新解析：短链改版导致的存量 item_id 失效
            # 因此被天然覆盖，不再需要「拿旧 id 失败后再解析一次」的补丁逻辑。
            report = self.service.fetch(product.product_url)
        except TbMonError as exc:
            log.warning(
                "Price fetch failed",
                error=str(exc),
                # AllStrategiesFailed.attempts 是已渲染好的字符串摘要
                attempts=[str(a) for a in (getattr(exc, "attempts", None) or [])],
            )
            self._product_repo.increment_fail_count(product.product_id)
            return False

        item = report.product
        if item is None:  # pragma: no cover - fetch 成功必然带 product
            log.error("Fetch reported success but carried no product")
            self._product_repo.increment_fail_count(product.product_id)
            return False

        price, price_note = self._resolve_monitored_price(item)
        if price is None:
            log.warning("No usable price", source=item.source, warnings=report.warnings)
            self._product_repo.increment_fail_count(product.product_id)
            return False
        if price_note:
            log.info("Price fallback used", note=price_note)

        # 短链每次重新解析，item_id 可能与存量不同（或由空变有），回写规范化
        if item.item_id and item.item_id != product.item_id:
            self._product_repo.update_item_id(product.product_id, item.item_id)
            product.item_id = item.item_id

        log.info(
            "Price fetched",
            price=str(price),
            original=str(item.price.original) if item.price.original is not None else None,
            method=item.source,
        )

        self._price_repo.insert_price(
            product_id=product.product_id,
            price=price,
            fetch_method=item.source,
            original_price=item.price.original,
        )
        self._record_snapshot(product.product_id, item, log)

        if product.monitor_status == MONITOR_STATUS_NOT_STARTED:
            return self._handle_first_monitor(product, price)

        return self._evaluate_rules(product, price, original_price=item.price.original)

    # ------------------------------------------------------------------ 内部
    @staticmethod
    def _resolve_monitored_price(product: ProductInfo) -> tuple[Decimal | None, str | None]:
        """取出用于监控的价格。

        多 SKU 区间价商品常常没有统一的实付价（current 为空），只有 low/high；
        这类商品很常见，只认 current 会让它们永久失败，故退化为取区间最低价。
        """
        if product.price.current is not None:
            return product.price.current, None
        if product.price.low is not None:
            return product.price.low, f"无统一实付价，取区间最低价 ¥{product.price.low}"
        return None, None

    def _record_snapshot(self, product_id: int, item: ProductInfo, log) -> None:
        """富数据（标题 / SKU / 参数 / 店铺 / 图片）落库，失败不影响价格监控。"""
        snapshot_id = self._snapshot_repo.insert_snapshot(product_id, item)
        if snapshot_id is None:
            log.warning("Snapshot not persisted")
        else:
            log.info("Snapshot persisted", snapshot_id=snapshot_id, source=item.source)

    def _handle_first_monitor(self, product: Product, price: Decimal) -> bool:
        """Handle first price recording for a new product."""
        self._product_repo.update_product_prices(
            product_id=product.product_id,
            current_price=float(price),
            initial_price=float(price),
            lowest_price=float(price),
        )
        self._product_repo.update_product_status(product.product_id, MONITOR_STATUS_MONITORING)
        logger.info("First monitor recorded", product_id=product.product_id, initial_price=str(price))
        return True

    def _evaluate_rules(self, product: Product, current_price: Decimal, original_price: Decimal | None = None) -> bool:
        """Evaluate all active rules for price changes."""
        rules = self._rule_repo.get_active_rules(product.product_id)
        if not rules:
            rules = [{"rule_id": None, "rule_type": "absolute_drop", "threshold_value": 0.01, "threshold_percent": None}]

        initial_price = self._price_repo.query_first_price(product.product_id)
        if initial_price is None:
            return False

        lowest = self._price_repo.query_lowest_price(product.product_id)
        self._product_repo.update_product_prices(
            product_id=product.product_id,
            current_price=float(current_price),
            lowest_price=float(lowest) if lowest else None,
        )

        triggered = False
        for rule in rules:
            if self._check_rule_triggered(rule, initial_price, current_price):
                triggered = True
                self._send_notification(product, rule, initial_price, current_price, original_price=original_price)

        if triggered:
            self._product_repo.update_product_status(product.product_id, MONITOR_STATUS_ENDED)

        return True

    def _check_rule_triggered(self, rule: dict, initial_price: Decimal, current_price: Decimal) -> bool:
        """Check if a monitoring rule has been triggered."""
        rule_type = rule.get("rule_type", "absolute_drop")

        if rule_type == "absolute_drop":
            threshold = Decimal(str(rule.get("threshold_value") or "0.01"))
            return (initial_price - current_price) >= threshold

        elif rule_type == "percent_drop":
            threshold_pct = Decimal(str(rule.get("threshold_percent") or "5"))
            if initial_price > 0:
                drop_pct = ((initial_price - current_price) / initial_price) * 100
                return drop_pct >= threshold_pct

        elif rule_type == "target_price":
            target = Decimal(str(rule.get("threshold_value") or "0"))
            return current_price <= target

        return False

    def _send_notification(
        self, product: Product, rule: dict,
        initial_price: Decimal, current_price: Decimal,
        original_price: Decimal | None = None,
    ) -> bool:
        """Send price drop notification email."""
        try:
            settings = self._settings
            reduction = initial_price - current_price

            # Show the listed price struck through when a subsidy/promo price
            # is detected; otherwise fall back to the first monitored price.
            promo_detected = original_price is not None and original_price > current_price
            listed_price = original_price if promo_detected else initial_price

            html_content = self._email_template.price_reduction(
                product_name=product.product_name,
                original_price=listed_price,
                current_price=current_price,
                reduction=reduction,
                product_url=product.product_url,
                initial_price=initial_price,
                promo_detected=promo_detected,
            )

            email_sender = EmailSender(
                email_host=settings.mail.host,
                email_sender=settings.mail.sender,
                email_license=settings.mail.license_key,
                email_receivers=product.notify_email,
                email_theme=f"【{product.product_name}】降价通知",
                email_content=html_content,
            )

            EmailService(email_sender).send()

            self._notification_repo.insert_notification(
                product_id=product.product_id,
                rule_id=rule.get("rule_id"),
                notify_type="email",
                notify_target=product.notify_email,
                notify_content=(
                    f"降价 {reduction} 元，当前到手价 {current_price}"
                    + (f"（优惠前 {original_price}）" if promo_detected else "")
                ),
                notify_status=1,
            )

            logger.info(
                "Notification sent",
                product_id=product.product_id,
                rule_type=rule.get("rule_type"),
                reduction=str(reduction),
            )
            return True

        except Exception as exc:
            logger.error("Send notification failed", error=str(exc))
            self._notification_repo.insert_notification(
                product_id=product.product_id,
                rule_id=rule.get("rule_id"),
                notify_type="email",
                notify_target=product.notify_email,
                notify_content=str(exc),
                notify_status=0,
            )
            return False

    def save_product_info(self, share_text: str, notify_email: str) -> int | None:
        """解析淘宝分享文本并落库为待监控商品；无法解析出链接或商品 ID 时返回 None。"""
        share = parse_share_text(share_text)
        if share is None:
            logger.error("Parse share text failed", reason="既无链接也无商品 ID")
            return None

        product_url = share.canonical_url
        if not product_url:
            logger.error("Parse share text failed", reason="无法构造商品链接")
            return None

        # 淘宝分享格式会变，标题缺失时用商品 ID 兜底，而不是让整条添加失败
        product_name = share.title or (
            f"淘宝商品 {share.item_id}" if share.item_id else "淘宝商品"
        )

        product_id = self._product_repo.insert_product(
            user_id=1,
            platform=share.platform or "淘宝",
            product_url=product_url,
            product_name=product_name,
            product_tk=share.tk,
            item_id=share.item_id,
            notify_email=notify_email,
        )

        if product_id:
            self._rule_repo.insert_rule(product_id, "absolute_drop", threshold_value=0.01)
        return product_id
