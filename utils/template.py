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
import os


class EmailTemplate(object):
    def __init__(self, template_info):
        """
        初始化
        :param template_info: dict类型 - 模板需要的信息：必须包含的字段有 template_name，其他字段根据模板需要定义
        """
        self.cur_path = os.path.abspath(os.path.dirname(__file__))
        self.root = self.cur_path[:self.cur_path.find("TaobaoProductMonitor") + len("TaobaoProductMonitor")]
        self.template_url = "resource/template"
        self.template_info = template_info

    def read_template(self):
        """
        读取模板
        :return:
        """
        file_path = self.root + os.path.sep + self.template_url + os.path.sep + self.template_info["template_name"]
        print(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            txt = f.read()
        return txt

    def price_reduction(self):
        """
        使用此模板需要包含以下字段：product_name, first_price, now_price, reduction, product_url
        :return:
        """
        read_template = self.read_template()
        return read_template.format(self.template_info["product_name"], self.template_info["first_price"],
                                    self.template_info["now_price"], self.template_info["reduction"], self.template_info["product_url"])


if __name__ == '__main__':
    dist = {"template_name": "price_reduction.html", "product_name": "1", "first_price": "2", "now_price": "3",
            "reduction": "4", "product_url": "4"}
    print(EmailTemplate(dist).price_reduction())
