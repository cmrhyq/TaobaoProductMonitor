"""
Taobao product price monitor service.
Integrates H5 API + Playwright price fetching with rule-based notifications.
"""

import re
from decimal import Decimal
from typing import Optional

import structlog

from config.settings import get_settings
from data.repository.product_repo import ProductRepository, MONITOR_STATUS_NOT_STARTED, MONITOR_STATUS_MONITORING, MONITOR_STATUS_ENDED
from data.repository.price_repo import PriceRepository
from data.repository.rule_repo import RuleRepository
from data.repository.notification_repo import NotificationRepository
from domain.entity.email import EmailSender
from data.models import Product
from service.monitor.price_fetcher import PriceFetcherService, PriceFetchResult, FetchMethod
from utils.email.send_email import EmailService
from utils.email.template import EmailTemplate

logger = structlog.get_logger(__name__)


class TaobaoMonitor:
    """
    Main monitoring service that orchestrates price checking,
    rule evaluation, and notifications.
    """

    def __init__(self):
        settings = get_settings()
        self._product_repo = ProductRepository()
        self._price_repo = PriceRepository()
        self._rule_repo = RuleRepository()
        self._notification_repo = NotificationRepository()
        self._settings = settings
        self._email_template = EmailTemplate()

        self._price_fetcher = PriceFetcherService(
            app_key=settings.taobao_api.app_key,
            proxy_url=settings.get_proxy_url(),
            api_timeout=settings.taobao_api.timeout,
            api_max_retries=settings.taobao_api.max_retries,
            api_request_interval=settings.taobao_api.request_interval,
            playwright_headless=settings.playwright.headless,
            playwright_timeout=settings.playwright.timeout,
        )

    def monitor_product(self, product: Product) -> bool:
        """
        Monitor a single product: fetch price, evaluate rules, send notifications.

        Returns:
            True if monitoring cycle completed successfully
        """
        log = logger.bind(product_id=product.product_id, product_name=product.product_name)
        log.info("Starting product monitor cycle")

        share_price = None
        if not product.item_id:
            link_info = self._price_fetcher.resolve_short_link(product.product_url)
            item_id = link_info.get("item_id")
            if item_id:
                self._product_repo.update_item_id(product.product_id, item_id)
                product.item_id = item_id
            share_price = link_info.get("price")

        result = self._price_fetcher.fetch_price(
            product_url=product.product_url,
            item_id=product.item_id,
        )

        if not result.success or result.price is None:
            if not share_price and ("tb.cn" in product.product_url):
                link_info = self._price_fetcher.resolve_short_link(product.product_url)
                share_price = link_info.get("price")
            if share_price:
                from decimal import Decimal as _Decimal
                log.info("Using share price from short link", price=share_price)
                result = PriceFetchResult(
                    price=_Decimal(share_price),
                    method=FetchMethod.API,
                    success=True,
                )
            else:
                log.warning("Price fetch failed", method=result.method.value, error=result.error_message)
                self._product_repo.increment_fail_count(product.product_id)
                return False

        current_price = result.price
        log.info("Price fetched", price=str(current_price), method=result.method.value)

        self._price_repo.insert_price(
            product_id=product.product_id,
            price=current_price,
            fetch_method=result.method.value,
        )

        if product.monitor_status == MONITOR_STATUS_NOT_STARTED:
            return self._handle_first_monitor(product, current_price)

        return self._evaluate_rules(product, current_price)

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

    def _evaluate_rules(self, product: Product, current_price: Decimal) -> bool:
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
                self._send_notification(product, rule, initial_price, current_price)

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
        initial_price: Decimal, current_price: Decimal
    ) -> bool:
        """Send price drop notification email."""
        try:
            settings = self._settings
            reduction = initial_price - current_price

            html_content = self._email_template.price_reduction(
                product_name=product.product_name,
                original_price=initial_price,
                current_price=current_price,
                reduction=reduction,
                product_url=product.product_url,
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
                notify_content=f"降价 {reduction} 元，当前价格 {current_price}",
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

    def save_product_info(self, share_text: str, notify_email: str) -> Optional[int]:
        """Parse Taobao share text and save as monitored product."""
        parse_result = self._parse_share_text(share_text)
        if not parse_result:
            return None

        product_id = self._product_repo.insert_product(
            user_id=1,
            platform=parse_result["platform"],
            product_url=parse_result["product_url"],
            product_name=parse_result["product_name"],
            product_tk=parse_result["product_tk"],
            item_id=None,
            notify_email=notify_email,
        )

        if product_id:
            self._rule_repo.insert_rule(product_id, "absolute_drop", threshold_value=0.01)
        return product_id

    @staticmethod
    def _parse_share_text(share_text: str) -> Optional[dict]:
        """Parse Taobao share text to extract product info."""
        try:
            platform = re.findall(r"【(.*?)】", share_text)[0]
            product_name = re.findall(r"「([^」]+)」", share_text)[0]
            product_url = re.findall(r'https?://[^\s]+', share_text)[0]

            from utils.common import get_url_params
            params = get_url_params(product_url)
            product_tk = params.get("tk", [""])[0]

            return {
                "platform": platform,
                "product_name": product_name,
                "product_url": product_url,
                "product_tk": product_tk,
            }
        except (IndexError, KeyError) as exc:
            logger.error("Parse share text failed", error=str(exc))
            return None
