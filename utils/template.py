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

from domain.entity.email import EmailParams
from domain.enums.base_enums import SystemEnum


class EmailTemplate(object):
    def __init__(self, template_info: EmailParams):
        """
        初始化
        :param template_info: EmailParams
        """
        self.template_url = "resource\\template"
        self.template_info = template_info

    def __read_template(self):
        """
        读取模板
        :return:
        """
        file_path = SystemEnum.PROJECT_BASE_PATH.name_value + os.path.sep + self.template_url + os.path.sep + self.template_info.template_name
        print(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            txt = f.read()
        return txt

    def price_reduction(self):
        """
        使用此模板需要包含以下字段：product_name, first_price, now_price, reduction, product_url
        :return:
        """
        read_template = self.__read_template()
        return read_template.format(self.template_info.template_name, self.template_info.first_price,
                                    self.template_info.new_price, self.template_info.reduction,
                                    self.template_info.product_url)
