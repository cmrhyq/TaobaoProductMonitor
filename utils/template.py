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


class EmailTemplate(object):
    def __init__(self, product_name, first_price, now_price, reduction, product_url):
        self.symbol = "%"
        self.product_name = product_name
        self.first_price = first_price
        self.now_price = now_price
        self.reduction = reduction
        self.product_url = product_url

    def price_reduction(self):
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>产品降价通知</title>
</head>
<body style="font-family: Arial, sans-serif;background-color: #f8f8f8;margin: 0;padding: 0;">
<div class="container" style="max-width: 600px;margin: 0 auto;padding: 20px;background-color: #ffffff;border-radius: 10px;box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);">
    <h3 style="color: #333333;text-align: center;">{}</h3>
    <p style="color: #666666;line-height: 1.6;margin-bottom: 20px;">首次监控价格{}</p>
    <p style="color: #666666;line-height: 1.6;margin-bottom: 20px;">当前监控价格{}</p>
    <p style="color: #666666;line-height: 1.6;margin-bottom: 20px;">已降价{}</p>
    <tr>
        <td align="center" valign="top" class="em_hide em_aside17"
            style="font-size: 0px; line-height: 0px; border-collapse: collapse;">
            <img src="http://cdn.mcauto-images-production.sendgrid.net/b6d0217aa232514a/04898e5e-fa43-4f6d-89a5-4e507ec31407/1054x14.png"
                 width="526" alt=""
                 style="display: block; max-width: 600px; color: rgb(255, 255, 255); border: 0px; outline: none;"
                 border="0"></td>
    </tr>
    <p style="text-align: center;color: #666666;line-height: 1.6;margin-bottom: 20px;"><a href="{}" style="display: inline-block;padding: 10px 20px;background-color: #4CAF50;color: #ffffff;text-decoration: none;border-radius: 5px;">了解更多</a></p>
</div>
</body>
</html>
        """.format(self.product_name, self.first_price, self.now_price, self.reduction, self.product_url)
