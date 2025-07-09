#!/usr/bin/env python
# -*- coding:utf-8 -*-
from __future__ import annotations

import re
import traceback
from contextlib import contextmanager
from decimal import Decimal
from typing import Optional

from loguru import logger
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By

from common.selenium_service import SeleniumService
from config.read_conf import ReadConfig
from dao.price_monitor_dao import PriceMonitorDao
from dao.product_dao import ProductDao
from domain.entity.email import EmailSender, ProductEmailInfo, EmailParams
from domain.entity.price import PriceInfo
from domain.entity.product import ProductInfo, ProductParseResult
from domain.entity.selenium import SeleniumBase
from domain.enums.base_enums import MonitorStatus, SystemEnum
from service.cookie.taobao_cookie import TaobaoCookie
from utils.common import get_url_params
from utils.send_email import EmailService
from utils.template import EmailTemplate


class TaobaoMonitor:
    PRICE_XPATH = '//*[@id="root"]/div/div[2]/div[2]/div/div[1]/div[2]/div[2]/div/span[2]'

    def __init__(self):
        self.rc = ReadConfig()
        self.browser = None
        self.product_dao = ProductDao()
        self.price_dao = PriceMonitorDao()
        self.taobao_cookie = TaobaoCookie()

    @contextmanager
    def _browser_context(self):
        """浏览器上下文管理器"""
        try:
            self.browser = SeleniumService()
            self.browser.start_browser(SeleniumBase(
                is_headless=False,
                is_cdp=True,
                is_dev=True,
                proxy="127.0.0.1:7890"
            ))
            yield self.browser
        finally:
            if self.browser:
                self.browser.close_browser()

    def __send_reduction_email(self, email_info: ProductEmailInfo) -> bool:
        """
        发送降价通知邮件
        
        Args:
            email_info: 邮件信息对象
            
        Returns:
            bool: 发送成功返回True，否则返回False
        """
        try:
            template_info = EmailParams(
                product_name=email_info.product_name,
                first_price=email_info.first_price,
                new_price=email_info.now_price,
                reduction=Decimal(email_info.first_price) - email_info.now_price,
                product_url=email_info.product_url
            )
            
            email_sender = EmailSender(
                email_host=self.rc.mail_host,
                email_sender=self.rc.mail_sender,
                email_license=self.rc.mail_license,
                email_receivers=email_info.notify_email,
                email_theme=f"【{email_info.product_name}】产品价格监控降价通知",
                email_content=EmailTemplate(template_info).price_reduction()
            )
            
            EmailService(email_sender).send()
            return True
        except Exception as e:
            logger.error(f"发送邮件失败，错误信息：{e}")
            return False

    def _parse_product_info(self, share_text: str) -> Optional[ProductParseResult]:
        """
        解析淘宝分享文本
        
        Args:
            share_text: 淘宝分享文本
            
        Returns:
            Optional[ProductParseResult]: 解析结果，解析失败返回None
        """
        try:
            platform = re.findall(r"【(.*?)】", share_text)[0]
            product_name = re.findall(r"「([^」]+)」", share_text)[0]
            product_url = re.findall(r'https?://[^\s]+', share_text)[0]
            product_tk = get_url_params(product_url)['tk'][0]

            logger.info(product_name)
            logger.info(product_url)
            
            return ProductParseResult(
                platform=platform,
                product_name=product_name,
                product_url=product_url,
                product_tk=product_tk
            )
        except (IndexError, KeyError) as e:
            logger.error(f"解析产品信息失败，错误信息：{e}")
            return None

    def save_product_info(self, share_text: str, notify_email: str) -> Optional[int]:
        """
        保存产品信息
        
        Args:
            share_text: 淘宝分享文本
            notify_email: 通知邮箱
            
        Returns:
            Optional[int]: 产品ID，保存失败返回None
        """
        parse_result = self._parse_product_info(share_text)
        if not parse_result:
            return None

        try:
            product_info = ProductInfo(
                platform=parse_result.platform,
                product_name=parse_result.product_name,
                product_url=parse_result.product_url,
                product_tk=parse_result.product_tk,
                notify_email=notify_email
            )
            return self.product_dao.insert_products(product_info)
        except Exception as e:
            logger.error(f"保存产品信息失败，错误信息：{e}")
            return None

    def _get_current_price(self, url: str) -> Optional[Decimal]:
        """
        获取当前价格
        
        Args:
            url: 商品URL
            
        Returns:
            Optional[Decimal]: 商品价格，获取失败返回None
        """
        try:
            with self._browser_context() as browser:

                # 首先登录一遍淘宝，获取cookie
                # self.taobao_cookie.get_cookie()
                # browser.wait_for_time(3)
                # tb_cookies = self.taobao_cookie.read_cookies()
                # # 向当前浏览器会话中添加一个cookie
                # for cookie in tb_cookies:
                #     browser.add_cookie({
                #         "domain": ".taobao.com",  # 这是cookie的域名、域名前有一个 . 表示对所有的子域名都有效
                #         "name": cookie,  # cookie名称
                #         "value": tb_cookies[cookie],  # cookie的值
                #         "path": '/',  # 这是cookie的路径。'/'表示该cookie对于域名的所有路径都是有效的
                #         "expires": None  # 这是cookie的过期时间。None表示该cookie没有过期时间，即它是一个会话cookie，当浏览器会话结束时它会被删除
                #     })

                browser.start_page(url)
                browser.wait_for_time(5)
                price_text = browser.find_element(By.XPATH, self.PRICE_XPATH).text
                return Decimal(price_text)
        except (NoSuchElementException, TimeoutException) as e:
            logger.error(f"获取价格失败，页面元素未找到：{e}")
            return None
        except Exception as e:
            logger.error(f"获取价格失败，错误信息：{e}")
            logger.error(traceback.format_exc())
            return None

    def _handle_first_monitor(self, product_info: ProductInfo, current_price: Decimal) -> bool:
        """处理首次监控"""
        price_info = PriceInfo(
            product_id=product_info.product_id,
            price=current_price
        )
        
        if self.price_dao.insert_price(price_info):
            product_info.monitor_status = MonitorStatus.MONITORING
            if self.product_dao.update_product_status(product_info):
                logger.info(f"开始监控产品：{product_info.product_name}，当前价格：{current_price}")
                return True
        return False

    def _handle_price_check(self, product_info: ProductInfo, current_price: Decimal) -> bool:
        """处理价格检查"""
        first_price_info = self.price_dao.query_first_price(product_info.product_id)
        if not first_price_info:
            return False

        if current_price < first_price_info.price:
            email_info = ProductEmailInfo(
                notify_email=product_info.notify_email,
                first_price=first_price_info.price,
                now_price=current_price,
                product_name=product_info.product_name,
                product_url=product_info.product_url
            )
            
            if self.__send_reduction_email(email_info):
                product_info.monitor_status = MonitorStatus.ENDED
                return self.product_dao.update_product_status(product_info)
        else:
            price_info = PriceInfo(
                product_id=product_info.product_id,
                price=current_price
            )
            if self.price_dao.insert_price(price_info):
                logger.info(f"检查产品监控的价格，最初价格：{first_price_info.price}，当前价格：{current_price}")
                return True
        return False

    def main(self, product_info: ProductInfo) -> bool:
        """
        监控商品价格

        Args:
            product_info: 商品信息

        Returns:
            bool: 监控成功返回True，否则返回False
        """
        logger.info(f"开始监控商品：{product_info.product_name}, url: {product_info.product_url}")
        current_price = self._get_current_price(product_info.product_url)
        if not current_price:
            return False

        try:
            if product_info.monitor_status == MonitorStatus.NOT_STARTED:
                return self._handle_first_monitor(product_info, current_price)
            else:
                return self._handle_price_check(product_info, current_price)
        except Exception as e:
            logger.error(f"监控价格失败，错误信息：{e}")
            return False


if __name__ == '__main__':
    a = """
    【淘宝】假一赔四 https://e.tb.cn/h.66AJ6K8SI7cqC6T?tk=FSE0VaGG7K7 HU071 「小米米家便携式即热式饮水机家用小型桌面台式直饮净水电热杯两用」
点击链接直接打开 或者 淘宝搜索直接打开
    """
    TaobaoMonitor().save_product_info(a, "cmrhyq@163.com")