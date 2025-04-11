from dataclasses import dataclass


@dataclass
class ProductInfo(object):
    """
    产品信息
    """
    product_id: int = None
    platform: str = None
    product_url: str = None
    product_name: str = None
    product_tk: str = None
    monitor_status: int = None
    notify_email: str = None

@dataclass
class EmailParams(object):
    """
    邮件模板
    """
    template_name: str = "price_reduction.html"
    product_name: str = None
    first_price: float = None
    new_price: float = None
    reduction: float = None
    product_url: str = None
    
    
@dataclass
class SendEmail(object):
    """
    邮件发送
    """
    notify_email: str = None
    first_price: float = None
    now_price: float = None
    product_name: str = None
    product_url: str = None