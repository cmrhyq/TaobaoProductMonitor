#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@File common.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/4/16 0:34
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import array
from urllib.parse import urlparse, parse_qs


def get_url_params(url: str):
    """
    获取ur中的参数
    :param url: url
    :return:
    """
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    return params
