#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@File template.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/4/17 0:44
@Author Alan Huang
@Version 0.0.1
@Description None
"""
from enum import Enum


class email_template(Enum):
    price_reduction = """
<html>
  <head></head>
  <body>
    <div class="">
        <p>你好，%s</p>
        <p>您监控的【%s】产品已降价，信息如下：</p>
        <div style="color:red;">一、降价信息</div>
        <div>
            <div style="font-size: 14px;line-height: 24px;" class="phoneFontSizeContent">· 首次监控价格%s</div>
            <div style="font-size: 14px;line-height: 24px;" class="phoneFontSizeContent">· 当前价格%s</div>
            <div style="font-size: 14px;line-height: 24px;" class="phoneFontSizeContent">· 降价了%s元</div>
        </div>
    </div>
  </body>
</html>
    """
