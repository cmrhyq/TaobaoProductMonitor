import datetime
from dataclasses import dataclass, field
from typing import Optional

from domain.enums.base_enums import MonitorStatus

@dataclass
class ProductParseResult:
    """淘宝产品解析结果"""
    platform: str
    product_name: str
    product_url: str
    product_tk: str


@dataclass
class ProductInfo:
    """
    产品信息
    """
    product_id: Optional[int] = None
    user_id: Optional[int] = None
    platform: Optional[str] = None
    product_url: Optional[str] = None
    product_name: Optional[str] = None
    product_tk: Optional[str] = None
    item_id: Optional[str] = None
    monitor_status: MonitorStatus = MonitorStatus.NOT_STARTED
    notify_email: Optional[str] = None
    initial_price: Optional[float] = None
    current_price: Optional[float] = None
    lowest_price: Optional[float] = None
    last_check_at: Optional[datetime.datetime] = None
    check_count: int = 0
    fail_count: int = 0
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    def __post_init__(self):
        """数据初始化后的处理"""
        if not self.created_at:
            self.created_at = datetime.datetime.now()
        if not self.updated_at:
            self.updated_at = self.created_at
        
        if isinstance(self.monitor_status, (int, str)):
            self.monitor_status = MonitorStatus.get_from_id(self.monitor_status) or MonitorStatus.NOT_STARTED

    def update_status(self, new_status: MonitorStatus) -> None:
        """
        更新监控状态
        
        Args:
            new_status: 新的监控状态
        """
        self.monitor_status = new_status
        self.updated_at = datetime.datetime.now()

    def is_valid(self) -> bool:
        """
        验证产品信息是否有效
        
        Returns:
            bool: 如果信息有效返回True，否则返回False
        """
        return all([
            self.product_id is not None,
            self.product_url is not None,
            self.product_name is not None,
            self.notify_email is not None
        ])

    def to_dict(self) -> dict:
        """
        转换为字典格式
        
        Returns:
            dict: 包含所有字段的字典
        """
        return {
            'product_id': self.product_id,
            'user_id': self.user_id,
            'platform': self.platform,
            'product_url': self.product_url,
            'product_name': self.product_name,
            'product_tk': self.product_tk,
            'item_id': self.item_id,
            'monitor_status': self.monitor_status.id if self.monitor_status else None,
            'notify_email': self.notify_email,
            'initial_price': self.initial_price,
            'current_price': self.current_price,
            'lowest_price': self.lowest_price,
            'last_check_at': self.last_check_at,
            'check_count': self.check_count,
            'fail_count': self.fail_count,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ProductInfo':
        """
        从字典创建实例

        Args:
            data: 包含产品信息的字典

        Returns:
            ProductInfo: 新的产品信息实例
        """
        if not isinstance(data, dict):
            if isinstance(data, (list, tuple)):
                field_names = [
                    'product_id', 'user_id', 'platform', 'product_url', 'product_name',
                    'product_tk', 'item_id', 'monitor_status', 'notify_email',
                    'initial_price', 'current_price', 'lowest_price',
                    'last_check_at', 'check_count', 'fail_count',
                    'created_at', 'updated_at',
                ]
                data_dict = {}
                for i, value in enumerate(data):
                    if i < len(field_names):
                        data_dict[field_names[i]] = value
                data = data_dict
            else:
                raise ValueError("Input must be a dictionary or a sequence")

        known_fields = {
            'product_id', 'user_id', 'platform', 'product_url', 'product_name',
            'product_tk', 'item_id', 'monitor_status', 'notify_email',
            'initial_price', 'current_price', 'lowest_price',
            'last_check_at', 'check_count', 'fail_count',
            'created_at', 'updated_at',
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)