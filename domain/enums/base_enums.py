from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, TypeVar, Type, Any, Generic

T = TypeVar('T', bound='BaseIdNameEnum')
ID = TypeVar('ID', int, str)

@dataclass
class EnumValue(Generic[ID]):
    id: ID
    name: str

class BaseIdNameEnum(Enum):
    """基础枚举类，包含id和名称属性"""

    @property
    def id(self):
        """返回枚举值的id"""
        return self.value.id

    @property
    def name_value(self):
        """返回枚举值的名称"""
        return self.value.name

    @classmethod
    def get_from_id(cls: Type[T], id_value: Any) -> Optional[T]:
        """根据id获取对应的枚举实例"""
        try:
            if id_value is not None:
                for enum_item in cls:
                    if enum_item.id == id_value:
                        return enum_item
        except (ValueError, TypeError):
            pass
        return None

    @classmethod
    def get_from_value(cls: Type[T], value: str) -> Optional[T]:
        """根据名称获取对应的枚举实例"""
        try:
            if value:
                for enum_item in cls:
                    if enum_item.name_value.lower() == value.lower():
                        return enum_item
        except Exception:
            pass
        print(f"未找到与 {value} 匹配的枚举值")
        return None

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self is other
        elif isinstance(other, (int, str)):
            return self.id == other or self.name_value.lower() == str(other).lower()
        return super().__eq__(other)

class SystemEnum(BaseIdNameEnum):
    PROJECT_BASE_PATH = EnumValue(1, str(Path(__file__).resolve().parent.parent))


class MonitorStatus(BaseIdNameEnum):
    NOT_STARTED = EnumValue(10, "未开始")
    MONITORING = EnumValue(11, "监控中")
    ENDED = EnumValue(12, "已结束")