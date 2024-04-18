# !/usr/bin/env python
# Author: AlanHuang
# Time: 2022/8/7 0:13
# Description: 
from selenium import webdriver


def config():
    """
    设置selenium的一些浏览器设置
    :return:
    """
    option = webdriver.ChromeOptions()
    # 添加UA
    option.add_argument('user-agent="MQQBrowser/26 Mozilla/5.0 (Linux; U; Android 2.3.7; zh-cn; MB200 Build/GRJ22; '
                        'CyanogenMod-7) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1"')
    # 设置屏幕分辨率
    option.add_argument('windows-size=2520x1680')
    # 谷歌文档提到需要加上这个来规避bug
    option.add_argument('--disable-gpu')
    # 隐藏滚动条
    # option.add_argument('--hide-scrollbars')
    # 不加载图片，提升速度
    # option.add_argument('blink-settings=imagesEnable=false')
    # 浏览器不提供可视化界面， linux下如果系统不支持可视化不加这条可能会启动失败
    option.add_argument('--headless')
    # 以最高权限运行
    option.add_argument('--no-sandbox')
    # 手动指定浏览器位置
    option.binary_location = r"driver\\msedgeriver.exe"
    # 添加crx插件
    # option.add_extension('d:\crx\AdBlock_v2.17.crx')
    # 禁用JavaScript
    # option.add_argument("--disable-javascript")
    # 设置开发者模式启动，该模式下webdriver属性为正常值
    option.add_experimental_option('excludeSwitches', ['enable-automation'])
    # 禁用浏览器弹窗
    prefs = {
        'profile.default_content_setting_values': {
            'notifications': 2
        }
    }
    option.add_argument('--disable-dev-shm-usage')
    option.add_experimental_option('prefs', prefs)
    driver = webdriver.Chrome(chrome_options=option)
