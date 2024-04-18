# !/usr/bin/env python
# Author: AlanHuang
# Time: 2022/8/7 13:47
# Description:
import yaml


def read_conf_yaml(path: str):
    """
    获取yaml文件配置
    :param: 配置文件路径
    :return: 配置信息
    """
    file = open(path, 'r', encoding='utf-8')
    content = yaml.load(file.read(), Loader=yaml.FullLoader)
    return content
