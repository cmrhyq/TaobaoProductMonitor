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
from database.data import query_monitor_products
from monitor.taobao import get_product_price


def product_monitor_task():
    dicts = query_monitor_products()
    for i in dicts:
        get_product_price(i)


if __name__ == '__main__':
    product_monitor_task()
