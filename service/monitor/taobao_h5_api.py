"""
Taobao H5 API client for fetching product prices.
Reverse-engineers the mtop.taobao.detail.getdetail/6.0 interface.
"""

import hashlib
import json
import re
import time
from decimal import Decimal
from typing import Optional
from urllib.parse import quote

import httpx
import structlog

logger = structlog.get_logger(__name__)

MTOP_BASE_URL = "https://h5api.m.taobao.com/h5"
API_NAME = "mtop.taobao.detail.getdetail"
API_VERSION = "6.0"
DEFAULT_APP_KEY = "12574478"


class TaobaoH5Api:
    """
    Taobao H5 API client using mtop interface.

    Handles cookie lifecycle, sign generation, and price extraction.
    """

    def __init__(
        self,
        app_key: str = DEFAULT_APP_KEY,
        proxy_url: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3,
        request_interval: float = 3.0,
    ):
        self._app_key = app_key
        self._proxy_url = proxy_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._request_interval = request_interval
        self._cookies: dict = {}
        self._token: Optional[str] = None
        self._last_request_time: float = 0.0

    def _generate_sign(self, token: str, timestamp: str, data: str) -> str:
        """
        Generate mtop sign parameter.
        sign = MD5(token & t & appKey & data)
        """
        sign_str = "&".join([token, timestamp, self._app_key, data])
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    def _extract_token_from_cookie(self, cookie_value: str) -> str:
        """Extract token from _m_h5_tk cookie value (part before first underscore)."""
        return cookie_value.split("_")[0]

    def _wait_for_interval(self) -> None:
        """Respect request interval to avoid rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)

    def _init_cookies(self, client: httpx.Client) -> bool:
        """
        Initialize cookies by making a preliminary request to get _m_h5_tk.

        Returns:
            True if cookies were successfully obtained
        """
        try:
            init_url = "https://h5api.m.taobao.com/h5/mtop.common.getTimestamp/1.0/"
            response = client.get(init_url, params={"api": "mtop.common.getTimestamp"})

            m_h5_tk = None
            for cookie_name, cookie_value in response.cookies.items():
                self._cookies[cookie_name] = cookie_value
                if cookie_name == "_m_h5_tk":
                    m_h5_tk = cookie_value

            if m_h5_tk:
                self._token = self._extract_token_from_cookie(m_h5_tk)
                logger.info("H5 API cookies initialized", token_prefix=self._token[:8])
                return True

            logger.warning("Failed to obtain _m_h5_tk cookie from init request")
            return False
        except Exception as exc:
            logger.error("Cookie initialization failed", error=str(exc))
            return False

    def _build_request_params(self, item_id: str) -> Optional[dict]:
        """Build the full request parameters with sign."""
        data = json.dumps({"itemNumId": str(item_id)}, separators=(",", ":"))
        timestamp = str(int(time.time() * 1000))

        if not self._token:
            logger.error("No token available for sign generation")
            return None

        sign = self._generate_sign(self._token, timestamp, data)

        params = {
            "jsv": "2.7.2",
            "appKey": self._app_key,
            "t": timestamp,
            "sign": sign,
            "api": API_NAME,
            "v": API_VERSION,
            "type": "originaljson",
            "timeout": "10000",
            "dataType": "json",
            "data": data,
        }
        return params

    def _parse_price_from_response(self, response_data: dict) -> Optional[Decimal]:
        """
        Extract price from mtop API response.

        The response structure varies, common paths:
        - data.item.price (simple)
        - data.apiStack[0].value -> JSON string -> price.price
        - data.price.price.priceText
        """
        try:
            data = response_data.get("data", {})

            # Path 1: direct price field
            item = data.get("item", {})
            if "price" in item:
                price_str = item["price"]
                return Decimal(str(price_str))

            # Path 2: apiStack contains nested JSON
            api_stack = data.get("apiStack", [])
            if api_stack:
                stack_value = api_stack[0].get("value", "")
                if isinstance(stack_value, str):
                    stack_data = json.loads(stack_value)
                else:
                    stack_data = stack_value

                price_info = stack_data.get("price", {})
                if isinstance(price_info, dict):
                    price_obj = price_info.get("price", {})
                    if isinstance(price_obj, dict):
                        price_text = price_obj.get("priceText", "")
                        if price_text:
                            clean_price = re.sub(r"[^\d.]", "", price_text)
                            if clean_price:
                                return Decimal(clean_price)
                    elif price_info.get("price"):
                        return Decimal(str(price_info["price"]))

                stack_item = stack_data.get("item", {})
                if "price" in stack_item:
                    return Decimal(str(stack_item["price"]))

            # Path 3: top-level price structure
            price_info = data.get("price", {})
            if isinstance(price_info, dict):
                price_val = price_info.get("price", {})
                if isinstance(price_val, dict):
                    price_text = price_val.get("priceText", "")
                    if price_text:
                        clean_price = re.sub(r"[^\d.]", "", price_text)
                        if clean_price:
                            return Decimal(clean_price)

            logger.warning("Could not extract price from response", keys=list(data.keys()))
            return None

        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            logger.error("Price parsing failed", error=str(exc))
            return None

    def get_product_price(self, item_id: str) -> Optional[Decimal]:
        """
        Fetch current price for a product by its item ID.

        Args:
            item_id: Taobao numeric item ID

        Returns:
            Product price as Decimal, or None on failure
        """
        transport = httpx.HTTPTransport(retries=1)
        proxy_config = {"all://": self._proxy_url} if self._proxy_url else None

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36"
            ),
            "Referer": "https://m.taobao.com/",
            "Accept": "application/json",
        }

        with httpx.Client(
            headers=headers,
            timeout=self._timeout,
            follow_redirects=True,
            proxies=proxy_config,
            transport=transport,
        ) as client:
            if not self._token:
                if not self._init_cookies(client):
                    return None

            for name, value in self._cookies.items():
                client.cookies.set(name, value, domain=".taobao.com")

            for attempt in range(self._max_retries):
                self._wait_for_interval()
                self._last_request_time = time.time()

                params = self._build_request_params(item_id)
                if not params:
                    return None

                try:
                    url = f"{MTOP_BASE_URL}/{API_NAME}/{API_VERSION}/"
                    response = client.get(url, params=params)

                    for cookie_name, cookie_value in response.cookies.items():
                        self._cookies[cookie_name] = cookie_value
                        if cookie_name == "_m_h5_tk":
                            self._token = self._extract_token_from_cookie(cookie_value)

                    if response.status_code != 200:
                        logger.warning(
                            "API returned non-200",
                            status=response.status_code,
                            attempt=attempt + 1,
                        )
                        self._token = None
                        self._init_cookies(client)
                        continue

                    resp_data = response.json()

                    ret_codes = resp_data.get("ret", [])
                    if any("SUCCESS" in str(r) for r in ret_codes):
                        price = self._parse_price_from_response(resp_data)
                        if price is not None:
                            logger.info(
                                "Price fetched via H5 API",
                                item_id=item_id,
                                price=str(price),
                            )
                            return price

                    if any(
                        "TOKEN_EMPTY" in str(r)
                        or "SID_INVALID" in str(r)
                        or "FAIL_SYS_TOKEN" in str(r)
                        for r in ret_codes
                    ):
                        logger.info("Token expired, refreshing", attempt=attempt + 1)
                        self._token = None
                        self._init_cookies(client)
                        continue

                    logger.warning(
                        "API returned error",
                        ret=ret_codes,
                        attempt=attempt + 1,
                    )

                except httpx.TimeoutException:
                    logger.warning("API request timeout", attempt=attempt + 1)
                except Exception as exc:
                    logger.error("API request failed", error=str(exc), attempt=attempt + 1)

        logger.error("All API attempts exhausted", item_id=item_id)
        return None

    def extract_item_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract numeric item ID from various Taobao URL formats.

        Supports:
        - https://item.taobao.com/item.htm?id=123456
        - https://detail.tmall.com/item.htm?id=123456
        - Short URLs (need to follow redirect)
        """
        match = re.search(r"[?&]id=(\d+)", url)
        if match:
            return match.group(1)

        if "tb.cn" in url or "m.tb.cn" in url:
            try:
                proxy_config = {"all://": self._proxy_url} if self._proxy_url else None
                with httpx.Client(
                    follow_redirects=True,
                    timeout=self._timeout,
                    proxies=proxy_config,
                ) as client:
                    response = client.get(url)
                    final_url = str(response.url)
                    match = re.search(r"[?&]id=(\d+)", final_url)
                    if match:
                        return match.group(1)
            except Exception as exc:
                logger.warning("Failed to resolve short URL", url=url, error=str(exc))

        return None
