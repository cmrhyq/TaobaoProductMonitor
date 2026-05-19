"""
Taobao H5 API client for fetching product prices.
Uses JSONP-based mtop API (no cookie/sign required) and mobile page scraping.
"""

import json
import re
import time
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

logger = structlog.get_logger(__name__)

MTOP_BASE_URL = "https://h5api.m.taobao.com/h5"
API_NAME = "mtop.taobao.detail.getdetail"
API_VERSION = "6.0"
DEFAULT_APP_KEY = "12574478"

DESKTOP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

PRICE_PATTERNS = [
    r'"price"\s*:\s*"([\d.]+)"',
    r'"priceText"\s*:\s*"([\d.]+)"',
    r'"originPrice"\s*:\s*"([\d.]+)"',
    r'"promotionPrice"\s*:\s*"([\d.]+)"',
    r'data-price="([\d.]+)"',
    r'"reservePrice"\s*:\s*"([\d.]+)"',
]


class TaobaoH5Api:
    """
    Taobao H5 API client.

    Strategy:
    1. JSONP-based mtop API call (no cookie/sign needed)
    2. Mobile page scraping as fallback
    """

    def __init__(
        self,
        app_key: str = DEFAULT_APP_KEY,
        proxy_url: Optional[str] = None,
        timeout: int = 15,
        max_retries: int = 3,
        request_interval: float = 3.0,
    ):
        self._app_key = app_key
        self._proxy_url = proxy_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._request_interval = request_interval
        self._last_request_time: float = 0.0

    def _wait_for_interval(self) -> None:
        """Respect request interval to avoid rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)

    def _fetch_via_jsonp_api(self, item_id: str) -> Optional[Decimal]:
        """Fetch price via JSONP-based H5 API (no cookie/token required)."""
        api_url = f"{MTOP_BASE_URL}/{API_NAME}/{API_VERSION}/"
        params = {
            "api": API_NAME,
            "v": API_VERSION,
            "ttid": "2022@taobao_liteAndroid_9.33.0",
            "type": "jsonp",
            "dataType": "jsonp",
            "data": json.dumps({"itemNumId": item_id}),
        }
        headers = {
            **DESKTOP_HEADERS,
            "Referer": f"https://h5.m.taobao.com/awp/core/detail.htm?id={item_id}",
        }

        try:
            with httpx.Client(
                timeout=self._timeout,
                proxy=self._proxy_url,
            ) as client:
                response = client.get(api_url, params=params, headers=headers)
                text = response.text

                json_match = re.search(r"mtopjsonp\d*\((.+)\)", text)
                if json_match:
                    resp_data = json.loads(json_match.group(1))
                else:
                    resp_data = json.loads(text)

                ret_codes = resp_data.get("ret", [])
                if any("SUCCESS" in str(r) for r in ret_codes):
                    return self._parse_price_from_response(resp_data)

                logger.warning("JSONP API returned non-success", ret=ret_codes)
                return None

        except (json.JSONDecodeError, httpx.TimeoutException) as exc:
            logger.warning("JSONP API request failed", error=str(exc))
            return None
        except Exception as exc:
            logger.error("JSONP API unexpected error", error=str(exc))
            return None

    def _fetch_via_mobile_page(self, item_id: str) -> Optional[Decimal]:
        """Fetch price by scraping the mobile product page HTML."""
        mobile_url = f"https://h5.m.taobao.com/awp/core/detail.htm?id={item_id}"

        try:
            with httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
                proxy=self._proxy_url,
            ) as client:
                response = client.get(mobile_url, headers=MOBILE_HEADERS)
                html = response.text

                for pattern in PRICE_PATTERNS:
                    match = re.search(pattern, html)
                    if match:
                        price = Decimal(match.group(1))
                        if Decimal("0.01") <= price <= Decimal("1000000"):
                            logger.info("Price fetched via mobile page", item_id=item_id, price=str(price))
                            return price

                logger.warning("No price found in mobile page", item_id=item_id)
                return None

        except Exception as exc:
            logger.error("Mobile page fetch failed", error=str(exc))
            return None

    def _parse_price_from_response(self, response_data: dict) -> Optional[Decimal]:
        """Extract price from mtop API response."""
        try:
            data = response_data.get("data", {})

            item = data.get("item", {})
            if "price" in item:
                return Decimal(str(item["price"]))

            price_info = data.get("price", {})
            if isinstance(price_info, dict):
                price_obj = price_info.get("price", {})
                if isinstance(price_obj, dict):
                    price_text = price_obj.get("priceText", "")
                    if price_text:
                        clean_price = re.sub(r"[^\d.]", "", price_text)
                        if clean_price:
                            return Decimal(clean_price)

            api_stack = data.get("apiStack", [])
            if api_stack:
                stack_value = api_stack[0].get("value", "")
                if isinstance(stack_value, str):
                    stack_data = json.loads(stack_value)
                else:
                    stack_data = stack_value

                stack_price_info = stack_data.get("price", {})
                if isinstance(stack_price_info, dict):
                    stack_price_obj = stack_price_info.get("price", {})
                    if isinstance(stack_price_obj, dict):
                        price_text = stack_price_obj.get("priceText", "")
                        if price_text:
                            clean_price = re.sub(r"[^\d.]", "", price_text)
                            if clean_price:
                                return Decimal(clean_price)
                    elif stack_price_info.get("price"):
                        return Decimal(str(stack_price_info["price"]))

                stack_item = stack_data.get("item", {})
                if "price" in stack_item:
                    return Decimal(str(stack_item["price"]))

            logger.warning("Could not extract price from response", keys=list(data.keys()))
            return None

        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            logger.error("Price parsing failed", error=str(exc))
            return None

    def get_product_price(self, item_id: str) -> Optional[Decimal]:
        """
        Fetch current price for a product by its item ID.

        Strategy:
        1. JSONP API (fast, no auth)
        2. Mobile page scraping (fallback)
        """
        self._wait_for_interval()
        self._last_request_time = time.time()

        price = self._fetch_via_jsonp_api(item_id)
        if price is not None:
            return price

        time.sleep(1)
        return self._fetch_via_mobile_page(item_id)

    def extract_item_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract numeric item ID from various Taobao URL formats.

        Supports:
        - https://item.taobao.com/item.htm?id=123456
        - https://detail.tmall.com/item.htm?id=123456
        - Short URLs (need to follow redirect or parse JS page)
        """
        match = re.search(r"[?&]id=(\d+)", url)
        if match:
            return match.group(1)

        if "tb.cn" in url or "m.tb.cn" in url:
            try:
                with httpx.Client(
                    follow_redirects=True,
                    timeout=self._timeout,
                    proxy=self._proxy_url,
                    headers=DESKTOP_HEADERS,
                ) as client:
                    response = client.get(url)
                    final_url = str(response.url)
                    match = re.search(r"[?&]id=(\d+)", final_url)
                    if match:
                        return match.group(1)
                    body_id_match = re.search(r"[?&]id=(\d+)", response.text)
                    if body_id_match:
                        return body_id_match.group(1)
            except Exception as exc:
                logger.warning("Failed to resolve short URL", url=url, error=str(exc))

        return None

    def resolve_short_link(self, url: str) -> dict:
        """
        Resolve a Taobao short link and extract all available info.

        Returns dict with keys: item_id, price, target_url (any may be None).
        """
        result = {}
        if "tb.cn" not in url and "m.tb.cn" not in url:
            match = re.search(r"[?&]id=(\d+)", url)
            if match:
                result["item_id"] = match.group(1)
            return result

        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=self._timeout,
                proxy=self._proxy_url,
                headers=DESKTOP_HEADERS,
            ) as client:
                response = client.get(url)
                html = response.text

                url_match = re.search(r"var\s+url\s*=\s*['\"](.+?)['\"]", html)
                if url_match:
                    target_url = url_match.group(1)
                    result["target_url"] = target_url
                    parsed = urlparse(target_url)
                    params = parse_qs(parsed.query)
                    if "id" in params:
                        result["item_id"] = params["id"][0]
                    if "price" in params:
                        result["price"] = params["price"][0]

                if "item_id" not in result:
                    body_id_match = re.search(r"[?&]id=(\d+)", html)
                    if body_id_match:
                        result["item_id"] = body_id_match.group(1)

        except Exception as exc:
            logger.warning("Failed to resolve short URL", url=url, error=str(exc))

        return result
