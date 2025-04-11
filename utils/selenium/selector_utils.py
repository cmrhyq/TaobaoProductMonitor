"""
@File selector_utils.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/6/21 16:22
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import re


# 获取选择器属性
def identify_selector_type(selector):
    if re.match(r'^#[\w-]+$', selector):
        return 'id'
    elif re.match(r'^[.\w-]+[\w-]*$', selector):
        return 'css'
    elif re.match(r'^(//.*|\(//.*|\*\[contains\(.*\)\]|\*\[@id=\'.*\'\])', selector):
        return 'xpath'
    elif re.match(r'^<[\w-]+>$', selector):
        return 'tag'
    elif re.match(r'^<a.*>.*</a>$', selector):
        return 'link'
    elif re.match(r'.*<a.*>.*</a>.*', selector):
        return 'partial link'
    elif re.match(r'^\[name=[\'\"].*[\'\"]\]$', selector):
        return 'name'
    elif re.match(r'^\[class=[\'\"].*[\'\"]\]$', selector):
        return 'class'
    else:
        return 'unknown'


# 获取选择器内容
def extract_value_from_selector(selector):
    match = re.match(r'^#([\w-]+)$', selector)
    if match:
        return match.group(1)

    match = re.match(r'^\.([\w-]+[\w-]*)$', selector)
    if match:
        return match.group(1)

    match = re.match(r'^(//.*|\(//.*|\*\[contains\((.*)\)\]|\*\[@id=\'(.*)\'\])', selector)
    if match:
        return match.group(1)

    match = re.match(r'^<([\w-]+)>$', selector)
    if match:
        return match.group(1)

    match = re.match(r'^<a.*>(.*)</a>$', selector)
    if match:
        return match.group(1)

    match = re.match(r'.*<a.*>(.*)</a>.*', selector)
    if match:
        return match.group(1)

    match = re.match(r'^\[name=[\'\"](.*)[\'\"]\]$', selector)
    if match:
        return match.group(1)

    match = re.match(r'^\[class=[\'\"](.*)[\'\"]\]$', selector)
    if match:
        return match.group(1)

    return None
