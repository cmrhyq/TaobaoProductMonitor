import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class PriceInfo:
    """
    商品价格信息
    """
    price_id: Optional[int] = None
    product_id: Optional[int] = None
    price: Optional[Decimal] = None
    gma_create: datetime.datetime = field(default_factory=datetime.datetime.now)
    gma_modified: datetime.datetime = field(default_factory=datetime.datetime.now)

    def __post_init__(self):
        """数据初始化后的处理"""
        # 确保时间字段有值
        if not self.gma_create:
            self.gma_create = datetime.datetime.now()
        if not self.gma_modified:
            self.gma_modified = self.gma_create

        # 确保价格为Decimal类型
        if self.price is not None and not isinstance(self.price, Decimal):
            self.price = Decimal(str(self.price))

    def is_valid(self) -> bool:
        """
        验证价格信息是否有效

        Returns:
            bool: 如果信息有效返回True，否则返回False
        """
        return all([
            self.product_id is not None,
            self.price is not None
        ])

    def update_price(self, new_price: float) -> bool:
        """
        更新价格

        Args:
            new_price: 新的价格值

        Returns:
            bool: 如果价格发生变化返回True，否则返回False
        """
        if self.price != Decimal(new_price):
            self.price = Decimal(str(new_price))
            self.gma_modified = datetime.datetime.now()
            return True
        return False

    def to_dict(self) -> dict:
        """
        转换为字典格式

        Returns:
            dict: 包含所有字段的字典
        """
        return {
            'price_id': self.price_id,
            'product_id': self.product_id,
            'price': float(self.price) if self.price else None,
            'gma_create': self.gma_create,
            'gma_modified': self.gma_modified
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PriceInfo':
        """
        从字典创建实例

        Args:
            data: 包含价格信息的字典

        Returns:
            PriceInfo: 新的价格信息实例
        """
        if not isinstance(data, dict):
            if isinstance(data, (list, tuple)):
                field_names = ['price_id', 'product_id', 'price',
                               'gma_create', 'gma_modified']
                data_dict = {}
                for i, value in enumerate(data):
                    if i < len(field_names):
                        data_dict[field_names[i]] = value
                data = data_dict
            else:
                raise ValueError("Input must be a dictionary or a sequence")

        return cls(**data)