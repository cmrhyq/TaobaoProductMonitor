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
    monitor_status: MonitorStatus = MonitorStatus.NOT_STARTED
    notify_email: Optional[str] = None
    gma_create: datetime.datetime = field(default_factory=datetime.datetime.now)
    gma_modified: datetime.datetime = field(default_factory=datetime.datetime.now)

    def __post_init__(self):
        """数据初始化后的处理"""
        # 确保时间字段有值
        if not self.gma_create:
            self.gma_create = datetime.datetime.now()
        if not self.gma_modified:
            self.gma_modified = self.gma_create
        
        # 将monitor_status转换为枚举类型
        if isinstance(self.monitor_status, (int, str)):
            self.monitor_status = MonitorStatus.get_from_id(self.monitor_status)

    def update_status(self, new_status: MonitorStatus) -> None:
        """
        更新监控状态
        
        Args:
            new_status: 新的监控状态
        """
        self.monitor_status = new_status
        self.gma_modified = datetime.datetime.now()

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
            'monitor_status': self.monitor_status.id if self.monitor_status else None,
            'notify_email': self.notify_email,
            'gma_create': self.gma_create,
            'gma_modified': self.gma_modified
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
                # Create a dictionary with available values
                field_names = ['product_id', 'user_id', 'platform', 'product_url', 'product_name',
                               'product_tk', 'monitor_status', 'notify_email', 'gma_create',
                               'gma_modified']
                data_dict = {}
                for i, value in enumerate(data):
                    if i < len(field_names):
                        data_dict[field_names[i]] = value
                data = data_dict
            else:
                raise ValueError("Input must be a dictionary or a sequence")

        return cls(**data)