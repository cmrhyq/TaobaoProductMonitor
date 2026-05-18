"""
Playwright-based price fetcher as fallback when H5 API fails.
Uses multiple selector strategies to extract prices from Taobao product pages.
"""

import re
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

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
    
    async def get_price(self, url: str) -> Optional[Decimal]:
        """
        Fetch product price by loading the page in a browser.
        
        Args:
            url: Product page URL
            
        Returns:
            Price as Decimal, or None on failure
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed, run: pip install playwright && playwright install chromium")
            return None
        
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
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                )
                
                # Stealth: hide webdriver property
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """)
                
                page = await context.new_page()
                page.set_default_timeout(self._timeout)
                
                logger.info("Navigating to product page", url=url)
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                
                price = await self._try_extract_price(page)
                
                if price is not None:
                    logger.info("Price fetched via Playwright", url=url, price=str(price))
                else:
                    logger.warning("Failed to extract price from page", url=url)
                
                return price
                
            except Exception as exc:
                logger.error("Playwright price fetch failed", url=url, error=str(exc))
                return None
            finally:
                await browser.close()
    
    async def _try_extract_price(self, page) -> Optional[Decimal]:
        """Try multiple strategies to extract price from page."""
        
        # Strategy 1: CSS selectors
        for selector in PRICE_SELECTORS:
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
        
        # Strategy 2: XPath patterns
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
        
        # Strategy 3: Full page text regex scan
        try:
            content = await page.content()
            prices = self._extract_prices_from_html(content)
            if prices:
                return prices[0]
        except Exception:
            pass
        
        return None
    
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
            except Exception:
                pass
        return None
    
    def _is_reasonable_price(self, price: Decimal) -> bool:
        """Sanity check: prices should be between 0.01 and 1,000,000."""
        return Decimal("0.01") <= price <= Decimal("1000000")
    
    def _extract_prices_from_html(self, html: str) -> list[Decimal]:
        """Extract candidate prices from page HTML using regex patterns."""
        patterns = [
            r'"price"\s*:\s*"?(\d+\.?\d*)"?',
            r'"priceText"\s*:\s*"(\d+\.?\d*)"',
            r'data-price="(\d+\.?\d*)"',
        ]
        
        prices = []
        for pattern in patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                try:
                    price = Decimal(match)
                    if self._is_reasonable_price(price):
                        prices.append(price)
                except Exception:
                    continue
        
        return sorted(set(prices))


def get_price_sync(url: str, **kwargs) -> Optional[Decimal]:
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
