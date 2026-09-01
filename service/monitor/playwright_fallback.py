"""
Playwright-based price fetcher as fallback when H5 API fails.
Uses multiple selector strategies to extract prices from Taobao product pages.

Returns dual-track prices:
- real price: the actual payable price (subsidized/promo price when detected)
- original price: the listed price before discounts (only when a discount is detected)
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

# Promo/subsidy price elements, extracted before the listed price so the
# discounted price wins.
PROMO_SELECTORS = [
    'span.tm-promo-price',
    'span[class*="promoPrice"]',
    'span[class*="promo-price"]',
    '[class*="PromoPrice"]',
]

PRICE_SELECTORS = [
    'span.tm-price',
    '[class*="Price"] span',
    '[class*="price"] span',
    'span[class*="priceText"]',
    '#J_StrPriceModBox .tb-rmb-num',
    '.tb-main-price .tm-price',
    'span.tm-promo-price',
]

PRICE_XPATH_PATTERNS = [
    '//*[@id="root"]//div[contains(@class, "price")]//span[contains(@class, "text")]',
    '//*[@id="root"]/div/div[2]/div[2]/div/div[1]/div[2]/div[2]/div/span[2]',
    '//span[contains(@class, "Price")]',
]

BASE_HTML_PATTERNS = [
    r'"price"\s*:\s*"?(\d+\.?\d*)"?',
    r'"priceText"\s*:\s*"[^"\d]*(\d+\.?\d*)"',
    r'data-price="(\d+\.?\d*)"',
]

PROMO_HTML_PATTERNS = [
    r'"promotionPrice"\s*:\s*"?(\d+\.?\d*)"?',
    r'"promotionPrice"\s*:\s*\{[^{}]*?"priceText"\s*:\s*"[^"\d]*(\d+\.?\d*)"',
    r'"promoPrice"\s*:\s*"?(\d+\.?\d*)"?',
    r'"promoPrice"\s*:\s*\{[^{}]*?"priceText"\s*:\s*"[^"\d]*(\d+\.?\d*)"',
    r'"skuPromoPrice"\s*:\s*"?(\d+\.?\d*)"?',
]

PRICE_REGEX = re.compile(r"(\d+\.?\d*)")


class PlaywrightPriceFetcher:
    """
    Fetches product prices using Playwright browser automation.
    Falls back through multiple selector strategies.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        slow_mo: int = 0,
        proxy_url: Optional[str] = None,
    ):
        self._headless = headless
        self._timeout = timeout
        self._slow_mo = slow_mo
        self._proxy_url = proxy_url

    async def get_price(self, url: str) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Fetch product prices by loading the page in a browser.

        Args:
            url: Product page URL

        Returns:
            (real_price, original_price); original is set only when a
            discount is detected. Both are None on failure.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed, run: pip install playwright && playwright install chromium")
            return None, None

        async with async_playwright() as p:
            browser_args = {
                "headless": self._headless,
                "slow_mo": self._slow_mo,
            }

            if self._proxy_url:
                browser_args["proxy"] = {"server": self._proxy_url}

            browser = await p.chromium.launch(**browser_args)

            try:
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/16.0 Mobile/15E148 Safari/604.1"
                    ),
                    viewport={"width": 375, "height": 812},
                )

                # Stealth: hide webdriver property
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """)

                page = await context.new_page()
                page.set_default_timeout(self._timeout)

                logger.info("Navigating to product page", url=url)
                await page.goto(url, wait_until="networkidle")
                await page.wait_for_timeout(8000)

                real, original = await self._try_extract_price(page)

                if real is not None:
                    logger.info(
                        "Price fetched via Playwright",
                        url=url,
                        price=str(real),
                        original=str(original) if original is not None else None,
                    )
                else:
                    logger.warning("Failed to extract price from page", url=url)

                return real, original

            except Exception as exc:
                logger.error("Playwright price fetch failed", url=url, error=str(exc))
                return None, None
            finally:
                await browser.close()

    async def _try_extract_price(self, page) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Try multiple strategies to extract (real, original) from page."""

        # Strategy 1: CSS selectors - promo price first, then listed price
        promo = await self._first_from_selectors(page, PROMO_SELECTORS)
        base = await self._first_from_selectors(page, PRICE_SELECTORS)

        # Strategy 2: XPath patterns for the listed price
        if base is None:
            base = await self._first_from_xpaths(page)

        if promo is not None or base is not None:
            return self._combine(promo, base)

        # Strategy 3: Full page HTML regex scan
        try:
            content = await page.content()
            return self._extract_prices_from_html(content)
        except Exception:
            pass

        return None, None

    async def _first_from_selectors(self, page, selectors) -> Optional[Decimal]:
        """First reasonable price found via CSS selectors."""
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.text_content()
                    if text:
                        price = self._parse_price_text(text)
                        if price and self._is_reasonable_price(price):
                            return price
            except Exception:
                continue
        return None

    async def _first_from_xpaths(self, page) -> Optional[Decimal]:
        """First reasonable price found via XPath patterns."""
        for xpath in PRICE_XPATH_PATTERNS:
            try:
                elements = await page.locator(f"xpath={xpath}").all()
                for element in elements:
                    text = await element.text_content()
                    if text:
                        price = self._parse_price_text(text)
                        if price and self._is_reasonable_price(price):
                            return price
            except Exception:
                continue
        return None

    @staticmethod
    def _combine(promo: Optional[Decimal], base: Optional[Decimal]) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Merge promo and listed candidates into (real, original).

        original is only set when the listed price is strictly higher,
        i.e. a real discount was detected.
        """
        if promo is not None and base is not None:
            if promo < base:
                return promo, base
            return base, None
        if promo is not None:
            return promo, None
        return base, None

    def _parse_price_text(self, text: str) -> Optional[Decimal]:
        """Parse a price value from text, handling currency symbols and ranges."""
        text = text.strip().replace("\u00a5", "").replace("\uffe5", "").replace(",", "")

        # Handle price ranges like "199.00-299.00" - take the lower
        if "-" in text:
            text = text.split("-")[0]

        match = PRICE_REGEX.search(text)
        if match:
            try:
                value = Decimal(match.group(1))
                if value > 0:
                    return value
            except (InvalidOperation, ValueError):
                pass
        return None

    def _is_reasonable_price(self, price: Decimal) -> bool:
        """Sanity check: prices should be between 0.01 and 1,000,000."""
        return Decimal("0.01") <= price <= Decimal("1000000")

    def _extract_prices_from_html(self, html: str) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Extract (real, original) from page HTML using regex patterns.

        Promo prices are scanned separately so a detected subsidy price
        wins over the lowest listed price.
        """
        base_values = set()
        for pattern in BASE_HTML_PATTERNS:
            for match in re.findall(pattern, html):
                try:
                    price = Decimal(match)
                except (InvalidOperation, ValueError):
                    continue
                if self._is_reasonable_price(price):
                    base_values.add(price)

        promo_values = set()
        for pattern in PROMO_HTML_PATTERNS:
            for match in re.findall(pattern, html):
                try:
                    price = Decimal(match)
                except (InvalidOperation, ValueError):
                    continue
                # <= on purpose: a promo dict's inner priceText is also caught
                # by the base priceText pattern, so an accepted promo can tie
                # min(base) without being a false positive.
                if self._is_reasonable_price(price) and (not base_values or price <= min(base_values)):
                    promo_values.add(price)

        real = min(promo_values) if promo_values else (
            min(base_values) if base_values else None
        )
        original = None
        if base_values and real is not None:
            highest = max(base_values)
            if highest > real:
                original = highest
        return real, original


def get_price_sync(url: str, **kwargs) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Synchronous wrapper for PlaywrightPriceFetcher."""
    import asyncio

    fetcher = PlaywrightPriceFetcher(**kwargs)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, fetcher.get_price(url))
                return future.result()
        else:
            return loop.run_until_complete(fetcher.get_price(url))
    except RuntimeError:
        return asyncio.run(fetcher.get_price(url))
