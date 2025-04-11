import decimal
from dataclasses import dataclass


@dataclass
class PriceInfo(object):
    price_id: int = None
    product_id: int = None
    price: decimal = None