from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class EmailSender:
    """Email sending configuration."""
    email_host: str = None
    email_sender: str = None
    email_receivers: str = None
    email_license: str = None
    email_theme: str = None
    email_content: str = None
    attachments: str = None


@dataclass
class ProductEmailInfo:
    """Product email notification info."""
    notify_email: str = None
    first_price: Decimal = None
    now_price: Decimal = None
    product_name: str = None
    product_url: str = None
