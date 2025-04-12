from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class EmailSender(object):
    """
    邮件发送器
    """
    email_host: str = None
    email_sender: str = None
    email_receivers: str = None
    email_license: str = None
    email_theme: str = None
    email_content: str = None
    attachments: str = None

@dataclass
class ProductEmailInfo(object):
    """
    邮件发送
    """
    notify_email: str = None
    first_price: Decimal = None
    now_price: Decimal = None
    product_name: str = None
    product_url: str = None

@dataclass
class EmailParams:
    """
    邮件模板
    """
    template_name: str = "price_reduction.html"
    product_name: Optional[str] = None
    first_price: Optional[Decimal] = None
    new_price: Optional[Decimal] = None
    reduction: Optional[Decimal] = None
    product_url: Optional[str] = None