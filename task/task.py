#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@File task.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/4/26 上午12:41
@Author Alan Huang
@Version 0.0.1
@Description None
"""
from service.monitor.taobao_monitor import TaobaoMonitor
from dao.product_dao import ProductDao


def product_monitor_task():
    product_dao = ProductDao()
    taobao = TaobaoMonitor()
    list_product_info = product_dao.query_monitor_products()
    for product_info in list_product_info:
        taobao.main(product_info)


if __name__ == '__main__':
    product_monitor_task()
