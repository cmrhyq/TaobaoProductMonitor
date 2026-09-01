"""
Taobao H5 API client for fetching product prices.
Uses JSONP-based mtop API (no cookie/sign required) and mobile page scraping.

Returns dual-track prices:
- real price: the actual payable price (subsidized/promo price when detected)
- original price: the listed price before discounts (only when a discount is detected)
"""

import json
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

logger = structlog.get_logger(__name__)

MTOP_BASE_URL = "https://h5api.m.taobao.com/h5"
API_NAME = "mtop.taobao.detail.getdetail"
API_VERSION = "6.0"
DEFAULT_APP_KEY = "12574478"

MIN_PRICE = Decimal("0.01")
MAX_PRICE = Decimal("1000000")

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

# Base (non-promo) price patterns for the mobile page. promotionPrice is
# deliberately absent here: promo prices are scanned separately so the
# discounted price wins over the listed one. [^"\d]* tolerates currency
# symbols inside JSON string values (e.g. "¥299.00").
PRICE_PATTERNS = [
    r'"price"\s*:\s*"[^"\d]*([\d.]+)"',
    r'"priceText"\s*:\s*"[^"\d]*([\d.]+)"',
    r'"originPrice"\s*:\s*"[^"\d]*([\d.]+)"',
    r'data-price="([\d.]+)"',
    r'"reservePrice"\s*:\s*"[^"\d]*([\d.]+)"',
]

# Subsidy/promo price patterns, including the {"priceText": "..."} dict form.
PROMO_PRICE_PATTERNS = [
    r'"promotionPrice"\s*:\s*"[^"\d]*([\d.]+)"',
    r'"promotionPrice"\s*:\s*\{[^{}]*?"priceText"\s*:\s*"[^"\d]*([\d.]+)"',
    r'"promoPrice"\s*:\s*"[^"\d]*([\d.]+)"',
    r'"promoPrice"\s*:\s*\{[^{}]*?"priceText"\s*:\s*"[^"\d]*([\d.]+)"',
    r'"skuPromoPrice"\s*:\s*"[^"\d]*([\d.]+)"',
    r'data-promo-price="([\d.]+)"',
]

# Keys collected by debug_price_info for diagnosing extraction problems.
PRICE_DEBUG_KEYS = {
    "price", "priceText", "originPrice", "promotionPrice",
    "promoPrice", "skuPromoPrice", "reservePrice",
}


def _is_reasonable(price: Decimal) -> bool:
    """Sanity check: prices should be between 0.01 and 1,000,000."""
    return MIN_PRICE <= price <= MAX_PRICE


def _to_decimal(value) -> Optional[Decimal]:
    """Parse a price from a bare str/int/float, stripping currency symbols."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            price = Decimal(str(value))
        except InvalidOperation:
            return None
        return price if _is_reasonable(price) else None
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]", "", value)
        if not cleaned or cleaned == ".":
            return None
        try:
            price = Decimal(cleaned)
        except InvalidOperation:
            return None
        return price if _is_reasonable(price) else None
    return None


def _price_from_node(node) -> Optional[Decimal]:
    """Parse a price from a bare value or a {priceText|price} dict node."""
    if isinstance(node, dict):
        for key in ("priceText", "price", "promoPrice", "promotionPrice"):
            if key in node:
                price = _to_decimal(node.get(key))
                if price is not None:
                    return price
        return None
    return _to_decimal(node)


def _collect_price_fields(node, path="data", out=None, depth=0) -> dict:
    """Walk a JSON tree and collect price-related fields for diagnostics."""
    if out is None:
        out = {}
    if len(out) >= 40 or depth > 10:
        return out
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                _collect_price_fields(value, f"{path}.{key}", out, depth + 1)
            elif key in PRICE_DEBUG_KEYS and value not in (None, ""):
                out[f"{path}.{key}"] = value
    elif isinstance(node, list):
        for index, value in enumerate(node[:20]):
            _collect_price_fields(value, f"{path}[{index}]", out, depth + 1)
    return out


def _scan_pattern_values(patterns, html: str, limit: int = 5) -> dict:
    """Collect raw captured values per pattern, for diagnostics."""
    result = {}
    for pattern in patterns:
        values = []
        for match in re.finditer(pattern, html):
            values.append(match.group(1))
            if len(values) >= limit:
                break
        if values:
            result[pattern] = values
    return result


class TaobaoH5Api:
    """
    Taobao H5 API client.

    Strategy:
    1. JSONP-based mtop API call (no cookie/sign needed)
    2. Mobile page scraping as fallback

    Both channels return (real_price, original_price); real_price prefers
    the subsidized/promo price whenever one can be detected.
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

    # ------------------------------------------------------------------
    # Channel 1: JSONP mtop API
    # ------------------------------------------------------------------

    def _request_jsonp(self, item_id: str) -> Optional[dict]:
        """Call the JSONP-based H5 API (no cookie/token required)."""
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
                return json.loads(json_match.group(1))
            return json.loads(text)

        except (json.JSONDecodeError, httpx.TimeoutException) as exc:
            logger.warning("JSONP API request failed", error=str(exc))
            return None
        except Exception as exc:
            logger.error("JSONP API unexpected error", error=str(exc))
            return None

    def _load_api_stack(self, data: dict) -> Optional[dict]:
        """Parse apiStack[0].value (a JSON string in most responses)."""
        stack = data.get("apiStack") or []
        if not stack:
            return None
        value = stack[0].get("value", "")
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value if isinstance(value, dict) else None

    def _extract_listed_price(self, data: dict) -> Optional[Decimal]:
        """The listed (pre-discount) price from item blocks."""
        sources = [data.get("item") or {}]
        stack = self._load_api_stack(data)
        if stack:
            sources.append(stack.get("item") or {})
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in ("price", "originPrice"):
                price = _price_from_node(source.get(key))
                if price is not None:
                    return price
        return None

    def _extract_displayed_price(self, data: dict) -> Optional[Decimal]:
        """The main price displayed on the mobile detail page."""
        roots = [data]
        stack = self._load_api_stack(data)
        if stack:
            roots.append(stack)

        for root in roots:
            price_info = root.get("price")
            if not isinstance(price_info, dict):
                continue
            price = _price_from_node(price_info.get("price"))
            if price is not None:
                return price
            price = _to_decimal(price_info.get("priceText"))
            if price is not None:
                return price
        return None

    def _extract_promo_price(
        self, data: dict, upper: Optional[Decimal]
    ) -> Optional[Decimal]:
        """Lowest accepted subsidy/promo price candidate.

        Candidates above `upper` (the displayed/listed price) are rejected:
        reference or crossed-out prices must not win.
        """
        nodes = []
        roots = [data]
        stack = self._load_api_stack(data)
        if stack:
            roots.append(stack)

        for root in roots:
            price_info = root.get("price")
            if isinstance(price_info, dict):
                nodes.append(price_info.get("promotionPrice"))
                extras = price_info.get("extraPrices")
                if isinstance(extras, list):
                    nodes.extend(extras)

            sku_core = root.get("skuCore")
            if isinstance(sku_core, dict):
                sku2info = sku_core.get("sku2info")
                if isinstance(sku2info, dict):
                    default_sku = sku2info.get("0")
                    if isinstance(default_sku, dict):
                        nodes.append(default_sku.get("promoPrice"))
                        nodes.append(default_sku.get("price"))

        candidates = []
        for node in nodes:
            price = _price_from_node(node)
            if price is not None and (upper is None or price < upper):
                candidates.append(price)
        return min(candidates) if candidates else None

    def _parse_prices_from_response(
        self, response_data: dict
    ) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Extract (real_price, original_price) from the mtop API response.

        real_price = promo price when detected, else the lowest of the
        displayed/listed prices. original_price is set only when the listed
        price is strictly higher than real_price (a discount was detected).
        """
        data = response_data.get("data") if isinstance(response_data, dict) else None
        if not isinstance(data, dict):
            return None, None

        listed = self._extract_listed_price(data)
        displayed = self._extract_displayed_price(data)

        base = [p for p in (displayed, listed) if p is not None]
        upper = min(base) if base else None
        promo = self._extract_promo_price(data, upper)

        if promo is not None:
            real = promo
        elif base:
            real = min(base)
        else:
            real = None
            logger.warning("Could not extract price from response", keys=list(data.keys()))

        original = listed if (listed is not None and real is not None and listed > real) else None
        return real, original

    def _fetch_via_jsonp_api(
        self, item_id: str
    ) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Fetch prices via the JSONP-based H5 API (no cookie/token required)."""
        resp_data = self._request_jsonp(item_id)
        if resp_data is None:
            return None, None

        ret_codes = resp_data.get("ret", [])
        if not any("SUCCESS" in str(r) for r in ret_codes):
            logger.warning("JSONP API returned non-success", ret=ret_codes)
            return None, None

        return self._parse_prices_from_response(resp_data)

    # ------------------------------------------------------------------
    # Channel 2: mobile page scraping
    # ------------------------------------------------------------------

    def _fetch_mobile_page_html(self, item_id: str) -> Optional[str]:
        """Fetch the mobile product page HTML."""
        mobile_url = f"https://h5.m.taobao.com/awp/core/detail.htm?id={item_id}"

        try:
            with httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
                proxy=self._proxy_url,
            ) as client:
                response = client.get(mobile_url, headers=MOBILE_HEADERS)
                return response.text

        except Exception as exc:
            logger.error("Mobile page fetch failed", error=str(exc))
            return None

    def _parse_prices_from_mobile_html(
        self, html: str
    ) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Extract (real_price, original_price) from mobile page HTML.

        Promo patterns are scanned separately from base patterns so a
        detected subsidy price wins over the listed one.
        """
        base_values = set()
        for pattern in PRICE_PATTERNS:
            for match in re.findall(pattern, html):
                price = _to_decimal(match)
                if price is not None:
                    base_values.add(price)

        promo_candidates = set()
        for pattern in PROMO_PRICE_PATTERNS:
            for match in re.findall(pattern, html):
                price = _to_decimal(match)
                # <= on purpose: a promo dict's inner priceText is also caught
                # by the base priceText pattern, so an accepted promo can tie
                # min(base) without being a false positive.
                if price is not None and (not base_values or price <= min(base_values)):
                    promo_candidates.add(price)

        real = min(promo_candidates) if promo_candidates else (
            min(base_values) if base_values else None
        )
        original = None
        if promo_candidates and base_values:
            highest = max(base_values)
            if highest > real:
                original = highest

        if real is None:
            logger.warning("No price found in mobile page")
        return real, original

    def _fetch_via_mobile_page(
        self, item_id: str
    ) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Fetch prices by scraping the mobile product page HTML."""
        html = self._fetch_mobile_page_html(item_id)
        if html is None:
            return None, None

        real, original = self._parse_prices_from_mobile_html(html)
        if real is not None:
            logger.info(
                "Price fetched via mobile page",
                item_id=item_id,
                price=str(real),
                original=str(original) if original is not None else None,
            )
        return real, original

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def get_product_prices(self, item_id: str) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Fetch (real_price, original_price) for a product by its item ID.

        Strategy:
        1. JSONP API (fast, no auth)
        2. Mobile page scraping (fallback)

        real_price is the subsidized/promo price when one is detected,
        otherwise the displayed price.
        """
        self._wait_for_interval()
        self._last_request_time = time.time()

        real, original = self._fetch_via_jsonp_api(item_id)
        if real is not None:
            return real, original

        time.sleep(1)
        return self._fetch_via_mobile_page(item_id)

    def get_product_price(self, item_id: str) -> Optional[Decimal]:
        """Fetch the current real (subsidy-aware) price. Legacy wrapper."""
        real, _ = self.get_product_prices(item_id)
        return real

    def debug_price_info(self, item_id: str) -> dict:
        """Collect per-channel extraction details for diagnostics.

        Used by `cli.py probe-price` to answer "why can't the subsidized
        price be extracted" on live items.
        """
        info = {"item_id": item_id, "jsonp": {}, "mobile_page": {}}

        resp_data = self._request_jsonp(item_id)
        if resp_data is None:
            info["jsonp"] = {"success": False, "error": "request failed or unparseable"}
        else:
            ret_codes = resp_data.get("ret", [])
            success = any("SUCCESS" in str(r) for r in ret_codes)
            real, original = (
                self._parse_prices_from_response(resp_data) if success else (None, None)
            )
            data = resp_data.get("data") if isinstance(resp_data, dict) else None
            info["jsonp"] = {
                "success": real is not None,
                "ret": ret_codes,
                "real": str(real) if real is not None else None,
                "original": str(original) if original is not None else None,
                "price_fields": _collect_price_fields(data) if isinstance(data, dict) else {},
            }

        html = self._fetch_mobile_page_html(item_id)
        if html is None:
            info["mobile_page"] = {"success": False, "error": "request failed"}
        else:
            real, original = self._parse_prices_from_mobile_html(html)
            info["mobile_page"] = {
                "success": real is not None,
                "real": str(real) if real is not None else None,
                "original": str(original) if original is not None else None,
                "html_size": len(html),
                "base_matches": _scan_pattern_values(PRICE_PATTERNS, html),
                "promo_matches": _scan_pattern_values(PROMO_PRICE_PATTERNS, html),
            }
        return info

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

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
