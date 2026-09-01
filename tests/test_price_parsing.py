"""
Unit tests for dual-track price extraction (issue #5).

Covers the pure parsing functions of every channel:
- mtop JSONP response parsing (TaobaoH5Api._parse_prices_from_response)
- mobile page HTML parsing (TaobaoH5Api._parse_prices_from_mobile_html)
- Playwright full-page HTML regex parsing (PlaywrightPriceFetcher._extract_prices_from_html)

Expected contract: real price prefers the detected subsidy/promo price;
original_price is only set when a listed price strictly higher than the
real price was found.
"""

import json
from decimal import Decimal

import pytest

from service.monitor.taobao_h5_api import TaobaoH5Api
from service.monitor.playwright_fallback import PlaywrightPriceFetcher


def D(value):
    return Decimal(value) if value is not None else None


class TestParsePricesFromResponse:
    """mtop JSONP structured response parsing."""

    def setup_method(self):
        self.api = TaobaoH5Api()

    def test_promotion_price_wins_over_listed_price(self):
        response = {
            "data": {
                "item": {"price": "299.00"},
                "price": {
                    "price": {"priceText": "¥299.00"},
                    "promotionPrice": {"priceText": "¥259.00"},
                },
            }
        }
        real, original = self.api._parse_prices_from_response(response)
        assert real == D("259.00")
        assert original == D("299.00")

    def test_promotion_price_inside_api_stack(self):
        stack_value = {
            "price": {
                "price": {"priceText": "¥199.00"},
                "promotionPrice": {"priceText": "¥159.00"},
            },
            "item": {"price": "199.00"},
        }
        response = {"data": {"apiStack": [{"value": json.dumps(stack_value)}]}}
        real, original = self.api._parse_prices_from_response(response)
        assert real == D("159.00")
        assert original == D("199.00")

    def test_extra_prices_lower_than_displayed_price(self):
        response = {
            "data": {
                "item": {"price": "399.00"},
                "price": {
                    "price": {"priceText": "¥399.00"},
                    "extraPrices": [{"priceText": "¥299.00"}],
                },
            }
        }
        real, original = self.api._parse_prices_from_response(response)
        assert real == D("299.00")
        assert original == D("399.00")

    def test_sku_core_default_sku_price(self):
        response = {
            "data": {
                "item": {"price": "259.00"},
                "price": {"price": {"priceText": "¥259.00"}},
                "skuCore": {"sku2info": {"0": {"price": {"priceText": "¥239.00"}}}},
            }
        }
        real, original = self.api._parse_prices_from_response(response)
        assert real == D("239.00")
        assert original == D("259.00")

    def test_no_promotion_keeps_displayed_price_without_original(self):
        response = {
            "data": {
                "item": {"price": "299.00"},
                "price": {"price": {"priceText": "¥299.00"}},
            }
        }
        real, original = self.api._parse_prices_from_response(response)
        assert real == D("299.00")
        assert original is None

    def test_reference_price_higher_than_displayed_is_rejected(self):
        response = {
            "data": {
                "item": {"price": "259.00"},
                "price": {
                    "price": {"priceText": "¥259.00"},
                    "extraPrices": [{"priceText": "¥399.00"}],
                },
            }
        }
        real, original = self.api._parse_prices_from_response(response)
        assert real == D("259.00")
        assert original is None

    def test_only_item_price_fallback(self):
        response = {"data": {"item": {"price": "88.00"}}}
        real, original = self.api._parse_prices_from_response(response)
        assert real == D("88.00")
        assert original is None

    def test_no_price_data(self):
        real, original = self.api._parse_prices_from_response({"data": {}})
        assert real is None
        assert original is None


class TestParsePricesFromMobileHtml:
    """Mobile detail page HTML regex parsing."""

    def setup_method(self):
        self.api = TaobaoH5Api()

    def test_promotion_price_wins(self):
        html = '<script>window.g_config={"price":"299.00","promotionPrice":"259.00"}</script>'
        real, original = self.api._parse_prices_from_mobile_html(html)
        assert real == D("259.00")
        assert original == D("299.00")

    def test_sku_promo_price_wins(self):
        html = '"price":"199.00","skuPromoPrice":"129.00"'
        real, original = self.api._parse_prices_from_mobile_html(html)
        assert real == D("129.00")
        assert original == D("199.00")

    def test_promo_price_dict_form(self):
        html = '"price":"199.00","promoPrice":{"priceText":"¥149.00"}'
        real, original = self.api._parse_prices_from_mobile_html(html)
        assert real == D("149.00")
        assert original == D("199.00")

    def test_base_price_with_currency_symbol(self):
        html = '"priceText":"¥88.00"'
        real, original = self.api._parse_prices_from_mobile_html(html)
        assert real == D("88.00")
        assert original is None

    def test_only_base_price(self):
        html = '"priceText":"88.00"'
        real, original = self.api._parse_prices_from_mobile_html(html)
        assert real == D("88.00")
        assert original is None

    def test_no_price_in_html(self):
        real, original = self.api._parse_prices_from_mobile_html("<html><body>empty</body></html>")
        assert real is None
        assert original is None

    def test_promo_price_not_lower_than_base_is_ignored(self):
        html = '"price":"199.00","promotionPrice":"299.00"'
        real, original = self.api._parse_prices_from_mobile_html(html)
        assert real == D("199.00")
        assert original is None


class TestPlaywrightHtmlExtraction:
    """Playwright full-page HTML regex parsing and candidate merging."""

    def setup_method(self):
        self.fetcher = PlaywrightPriceFetcher()

    def test_promotion_price_wins_over_base(self):
        html = '"price":"299.00","promotionPrice":"259.00"'
        real, original = self.fetcher._extract_prices_from_html(html)
        assert real == D("259.00")
        assert original == D("299.00")

    def test_no_promotion(self):
        html = '"priceText":"88.00"'
        real, original = self.fetcher._extract_prices_from_html(html)
        assert real == D("88.00")
        assert original is None

    def test_combine_promo_lower(self):
        assert PlaywrightPriceFetcher._combine(D("100"), D("200")) == (D("100"), D("200"))

    def test_combine_promo_equal_base(self):
        assert PlaywrightPriceFetcher._combine(D("200"), D("200")) == (D("200"), None)

    def test_combine_promo_only(self):
        assert PlaywrightPriceFetcher._combine(D("100"), None) == (D("100"), None)

    def test_combine_base_only(self):
        assert PlaywrightPriceFetcher._combine(None, D("200")) == (D("200"), None)

    def test_parse_price_text_currency_and_ranges(self):
        assert self.fetcher._parse_price_text("¥1,299.00") == D("1299.00")
        assert self.fetcher._parse_price_text("199.00-299.00") == D("199.00")
        assert self.fetcher._parse_price_text("no price") is None
