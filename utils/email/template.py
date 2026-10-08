"""
Email template rendering using Jinja2.
Singleton pattern with custom filters for currency formatting.
"""

from decimal import Decimal

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config.settings import PROJECT_ROOT

logger = structlog.get_logger(__name__)

TEMPLATE_DIR = PROJECT_ROOT / "resource" / "template"

Numeric = Decimal | float | int | str


def _currency_filter(value: Numeric) -> str:
    """Format a numeric value as currency with 2 decimal places."""
    try:
        return f"{float(value):.2f}"
    except (ValueError, TypeError):
        return str(value)


def _percent_filter(value: Numeric) -> str:
    """Format a numeric value as percentage with 1 decimal place."""
    try:
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return str(value)


class EmailTemplate:
    """Singleton template renderer with Jinja2 and custom filters."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._env = Environment(
                loader=FileSystemLoader(str(TEMPLATE_DIR)),
                autoescape=select_autoescape(["html"]),
            )
            cls._instance._env.filters["currency"] = _currency_filter
            cls._instance._env.filters["percent"] = _percent_filter
        return cls._instance

    def render(self, template_name: str, **context) -> str:
        """Render a template file with the given context variables."""
        try:
            template = self._env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error("Template render failed", template=template_name, error=str(e))
            return ""

    def price_reduction(
        self,
        product_name: str,
        original_price: Numeric,
        current_price: Numeric,
        reduction: Numeric,
        product_url: str,
        initial_price: Numeric = None,
        promo_detected: bool = False,
    ) -> str:
        """Render price reduction notification email with computed percentage.

        original_price is the displayed (struck-through) price; initial_price
        is the monitoring baseline used for the drop percentage.
        """
        orig = float(original_price)
        curr = float(current_price)
        drop = float(reduction)
        basis = float(initial_price) if initial_price is not None else orig
        drop_percent = (drop / basis * 100) if basis > 0 else 0

        return self.render(
            "price_reduction.html",
            product_name=product_name,
            original_price=orig,
            current_price=curr,
            reduction=drop,
            drop_percent=drop_percent,
            product_url=product_url,
            promo_detected=promo_detected,
        )
