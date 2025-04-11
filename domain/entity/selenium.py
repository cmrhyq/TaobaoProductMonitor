from dataclasses import dataclass

from selenium.webdriver.support.wait import WebDriverWait

from domain.enums.base_enums import LocateElementMethod


@dataclass
class InitOptions(object):
    """
    初始化选项
    """
    headless: bool = False


@dataclass
class LocateElementOptions(object):
    """
    定位元素选项
    wait (WebDriverWait): WebDriverWait 对象，用于显示等待元素出现
    by: 元素定位方式（例如 By.ID，By.XPATH）。
    value: 元素定位值（例如元素的 ID，XPath 表达式）。
    method (str): 操作方法（默认为 None）。
    key: 输入文本的值（默认为 None）。
    is_more (bool): 是否返回多个元素，默认为 False。
    check_visibility (bool): 是否检查元素可见性（默认为 False）。
    """
    wait: WebDriverWait
    by: str = 'xpath'
    value: str = None
    method: LocateElementMethod = None
    key: str = None
    is_more: bool = False
    check_visibility: bool = False