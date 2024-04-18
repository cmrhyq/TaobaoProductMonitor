#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@File taobao.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/4/16 0:17
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import os.path
import re
from time import sleep

from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from config.read_yaml import read_conf_yaml
from database.data import insert_products, query_price_count, query_first_price, insert_price, update_product_status
from utils.common import get_url_params
from utils.send_email import send
from utils.template import EmailTemplate

curPath = os.path.abspath(os.path.dirname(__file__))
root = curPath[:curPath.find("TaobaoProductMonitor") + len("TaobaoProductMonitor")]

sysConf = read_conf_yaml(root + os.path.sep + 'config/web_config.yaml')
path = Service(sysConf['webInterface']['chrome']['path'])
browser = webdriver.Chrome(service=path)


def get_product_price(info: dict):
    """
    监控产品价格信息
    :param info: 必须包含以下内容 {"product_id":12,"platform":"","product_name":"","product_url":"","product_url":"","notify_email":""}
    :return:
    """
    browser.maximize_window()
    browser.get(info['product_url'])
    logger.info("开始监控%s的价格" % info['product_url'])
    sleep(3)
    now_price = float(browser.find_element(By.XPATH, '//*[@id="detail_container"]/div[3]/div[1]/div[1]/div[2]').text)
    product_id = info['product_id']
    monitor_count = query_price_count(product_id)['count']
    if monitor_count > 0:
        price_info = query_first_price(product_id)
        first_price = price_info['price']
        if now_price < first_price:
            host = sysConf['mail']['host']
            sender = sysConf['mail']['sender']
            receivers = info["notify_email"]
            licenses = sysConf['mail']['license']
            theme = """【%s】产品价格监控降价通知""" % info["product_name"]
            template = EmailTemplate(info["product_name"], first_price, now_price, float(first_price) - now_price, info['product_url'])
            send(host, sender, receivers, licenses, theme, template.price_reduction())
            update_product_status(product_id, 12)
        else:
            price_id = insert_price(product_id, now_price)
            if price_id is not None:
                logger.info("""第%s次监控价格，最初价格：%s，当前价格：%s""" % (monitor_count + 1, first_price, now_price))
            else:
                logger.warning("价格监控数据插入失败")
    else:
        price_id = insert_price(product_id, now_price)
        if price_id is not None:
            update_product_status(product_id, 11)
            logger.info("""开始监控产品：%s，当前价格：%s""" % (info['product_name'], now_price))
        else:
            logger.warning("价格监控数据插入失败")


def save_product_info(product_info: str, notify_email: str):
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
    resultDict = {}
    platform = re.findall(r"【(.*?)】", product_info)[0]
    product_name = re.findall(r"「([^」]+)」", product_info)[0]
    product_url = re.findall(r'https?://[^\s]+', product_info)[0]
    product_tk = get_url_params(product_url)['tk'][0]
    product_id = insert_products(platform, product_name, product_url, product_tk, notify_email)
    if product_id is not None:
        resultDict['platform'] = platform
        resultDict['product_name'] = product_name
        resultDict['product_url'] = product_url
        resultDict['product_tk'] = product_tk
        resultDict['product_id'] = product_id
        return resultDict
    else:
        logger.warning("产品数据插入失败")
        return resultDict
