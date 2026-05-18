"""
Unified price fetching service with strategy pattern.
Tries H5 API first, falls back to Playwright on failure.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

import structlog

from service.monitor.taobao_h5_api import TaobaoH5Api
from service.monitor.playwright_fallback import PlaywrightPriceFetcher, get_price_sync

logger = structlog.get_logger(__name__)


class FetchMethod(str, Enum):
    """Price fetch method identifier."""
    API = "api"
    PLAYWRIGHT = "playwright"
    UNKNOWN = "unknown"


@dataclass
class PriceFetchResult:
    """Result of a price fetch attempt."""
    price: Optional[Decimal]
    method: FetchMethod
    success: bool
    error_message: Optional[str] = None


class PriceFetcherService:
    """
    Orchestrates price fetching with fallback strategy.
    
    Priority:
    1. H5 API (fast, lightweight)
    2. Playwright browser automation (reliable fallback)
    """
    
    def __init__(
        self,
        app_key: str = "12574478",
        proxy_url: Optional[str] = None,
        api_timeout: int = 10,
        api_max_retries: int = 3,
        api_request_interval: float = 3.0,
        playwright_headless: bool = True,
        playwright_timeout: int = 30000,
    ):
        self._h5_api = TaobaoH5Api(
            app_key=app_key,
            proxy_url=proxy_url,
            timeout=api_timeout,
            max_retries=api_max_retries,
            request_interval=api_request_interval,
        )
        self._playwright_kwargs = {
            "headless": playwright_headless,
            "timeout": playwright_timeout,
            "proxy_url": proxy_url,
        }
    
    def fetch_price(self, product_url: str, item_id: Optional[str] = None) -> PriceFetchResult:
        """
        Fetch product price using the best available method.
        
        Args:
            product_url: Full product URL
            item_id: Taobao numeric item ID (if already known)
            
        Returns:
            PriceFetchResult with price and method used
        """
        # Try H5 API first
        if item_id or self._can_extract_item_id(product_url):
            result = self._try_h5_api(product_url, item_id)
            if result.success:
                return result
            logger.info(
                "H5 API failed, falling back to Playwright",
                url=product_url,
                error=result.error_message,
            )
        
        # Fallback to Playwright
        return self._try_playwright(product_url)
    
    def _can_extract_item_id(self, url: str) -> bool:
        """Check if we can potentially extract an item ID from the URL."""
        return "id=" in url or "tb.cn" in url or "m.tb.cn" in url
    
    def _try_h5_api(self, product_url: str, item_id: Optional[str] = None) -> PriceFetchResult:
        """Attempt to fetch price via H5 API."""
        try:
            if not item_id:
                item_id = self._h5_api.extract_item_id_from_url(product_url)
            
            if not item_id:
                return PriceFetchResult(
                    price=None,
                    method=FetchMethod.API,
                    success=False,
                    error_message="Could not extract item_id from URL",
                )
            
            price = self._h5_api.get_product_price(item_id)
            
            if price is not None:
                return PriceFetchResult(
                    price=price,
                    method=FetchMethod.API,
                    success=True,
                )
            
            return PriceFetchResult(
                price=None,
                method=FetchMethod.API,
                success=False,
                error_message="API returned no price data",
            )
            
        except Exception as exc:
            return PriceFetchResult(
                price=None,
                method=FetchMethod.API,
                success=False,
                error_message=str(exc),
            )
    
    def _try_playwright(self, product_url: str) -> PriceFetchResult:
        """Attempt to fetch price via Playwright."""
        try:
            price = get_price_sync(product_url, **self._playwright_kwargs)
            
            if price is not None:
                return PriceFetchResult(
                    price=price,
                    method=FetchMethod.PLAYWRIGHT,
                    success=True,
                )
            
            return PriceFetchResult(
                price=None,
                method=FetchMethod.PLAYWRIGHT,
                success=False,
                error_message="Playwright could not extract price from page",
            )
            
        except Exception as exc:
            return PriceFetchResult(
                price=None,
                method=FetchMethod.PLAYWRIGHT,
                success=False,
                error_message=str(exc),
            )
    
    def resolve_item_id(self, product_url: str) -> Optional[str]:
        """
        Resolve a product URL to its numeric item ID.
        Useful for storing the ID for faster future lookups.
        """
        return self._h5_api.extract_item_id_from_url(product_url)
