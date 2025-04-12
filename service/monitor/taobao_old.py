#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@File taobao_monitor.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/4/16 0:17
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import os
import re
from time import sleep

from loguru import logger
from selenium.webdriver.common.by import By

from common.selenium_service import SeleniumService
from config.read_conf import ReadConfig
from dao.price_monitor_dao import PriceMonitorDao
from dao.product_dao import ProductDao
from domain.entity.email import EmailSender, ProductEmailInfo, EmailParams
from domain.entity.price import PriceInfo
from domain.entity.product import ProductInfo
from domain.enums.base_enums import MonitorStatus
from utils.common import get_url_params
from utils.send_email import EmailService
from utils.template import EmailTemplate


class TaobaoMonitor:
    def __init__(self):
        self.rc = ReadConfig()
        self.browser = SeleniumService(proxy=True)
        self.product_dao = ProductDao()
        self.price_dao = PriceMonitorDao()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.browser.close_browser()

    def __send_reduction_email(self, email_info: ProductEmailInfo):
        try:
            # 构建邮件信息
            host = self.rc.mail_host
            sender = self.rc.mail_sender
            receivers = email_info.notify_email
            licenses = self.rc.mail_license
            theme = f"【{email_info.product_name}】产品价格监控降价通知"

            # 构建模板
            template_info = EmailParams(
                product_name=email_info.product_name,
                first_price=email_info.first_price,
                new_price=email_info.now_price,
                reduction=float(email_info.first_price) - email_info.now_price,
                product_url=email_info.product_url
            )
            template = EmailTemplate(template_info)

            email_info = EmailSender(
                email_host=host,
                email_sender=sender,
                email_license=licenses,
                email_receivers=receivers,
                email_theme=theme,
                email_content=template.price_reduction()
            )
            EmailService(email_info).send()
        except Exception as e:
            logger.error(f"发送邮件失败，错误信息：{e}")

    def _save_product_info(self, product_info: str, notify_email: str):
        """
        解析淘宝分享链接并保存产品信息
        :param notify_email: 通知邮箱地址
        :param product_info: 产品信息
        <div>
        【淘宝】https://m.tb.cn/h.5zxz3j69cN5go4k?tk=XUymWKIqxIz MF6563 「优衣库女装网眼V领短针织开衫长袖薄外套空调衫2024新款468541」
    点击链接直接打开 或者 淘宝搜索直接打开
        </div>
        :return:
        """
        try:
            platform = re.findall(r"【(.*?)】", product_info)[0]
            product_name = re.findall(r"「([^」]+)」", product_info)[0]
            product_url = re.findall(r'https?://[^\s]+', product_info)[0]
            product_tk = get_url_params(product_url)['tk'][0]

            product_info = ProductInfo(
                platform=platform,
                product_name=product_name,
                product_url=product_url,
                product_tk=product_tk,
                notify_email=notify_email
            )
            product_id = self.product_dao.insert_products(product_info)
            return product_id
        except Exception as e:
            logger.error(f"解析产品信息失败，错误信息：{e}")

    def get_product_price(self, product_info: ProductInfo):
        """
        监控产品价格信息
        :param product_info: 产品监控信息
        :return:
        """
        try:
            self.browser.start_page(product_info.product_url)
            logger.info("开始监控%s的价格" % product_info.product_url)
            sleep(3)
            now_price = float(self.browser.find_element(By.XPATH, '//*[@id="root"]/div/div[2]/div[2]/div/div[1]/div[2]/div[2]/div/span[2]').text)
            product_id = product_info.product_id
            # 产品状态 != 0 未开始
            if product_info.monitor_status != MonitorStatus.NOT_STARTED:
                # 获取产品第一次开始监控的价格
                price_info = self.price_dao.query_first_price(product_id)
                first_price = price_info.price
                # 如果第一次开始监控的价格大于当前价格，说明产品降价了
                # 降价了就发送邮件，更新监控状态
                if now_price < first_price:
                    email_info = ProductEmailInfo(
                        notify_email=product_info.notify_email,
                        first_price=first_price,
                        now_price=now_price,
                        product_name=product_info.product_name,
                        product_url=product_info.product_url
                    )
                    self.__send_reduction_email(email_info)

                    # 更新产品状态
                    product_info = ProductInfo(
                        product_id=product_id,
                        monitor_status=MonitorStatus.ENDED
                    )
                    self.product_dao.update_product_status(product_info)
                else:
                    # 没有降价就新增一条监控数据
                    price_info_update = PriceInfo(
                        product_id=product_id,
                        price=now_price
                    )
                    price_id = self.price_dao.insert_price(price_info_update)
                    if price_id is not None:
                        logger.info(f"检查产品监控的价格，最初价格：{first_price}，当前价格：{now_price}")
                    else:
                        logger.warning("价格监控数据插入失败")
            else:
                price_info_update = PriceInfo(
                    product_id=product_id,
                    price=now_price
                )
                price_id = self.price_dao.insert_price(price_info_update)
                if price_id is not None:
                    # 更新产品状态
                    product_info = ProductInfo(
                        product_id=product_id,
                        monitor_status=MonitorStatus.MONITORING
                    )
                    self.product_dao.update_product_status(product_info)
                    logger.info(f"开始监控产品：{product_info.product_name}，当前价格：{now_price}")
                else:
                    logger.warning("价格监控数据插入失败")
        except Exception as e:
            logger.error(f"获取产品价格出现错误{e}")


if __name__ == '__main__':
    link = """
    【淘宝】假一赔四 https://e.tb.cn/h.66AJ6K8SI7cqC6T?tk=FSE0VaGG7K7 HU071 「小米米家便携式即热式饮水机家用小型桌面台式直饮净水电热杯两用」
点击链接直接打开 或者 淘宝搜索直接打开
    """
    TaobaoMonitor()._save_product_info(link, "cmrhyq@163.com")