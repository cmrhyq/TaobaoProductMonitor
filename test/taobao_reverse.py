# -*- coding: utf-8 -*-
"""
1、先手动登录获取cookie
2、获取cookie保存在taobaoCookies.pickle 文件中
3、使用cookie去请求网页

"""
import os
import pickle
import time

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait

brower = webdriver.Chrome()
wait = WebDriverWait(brower, 10)


# 获取driver打开浏览器的对象
def get_browser():
    options = webdriver.ChromeOptions()
    # 打开开发者模式
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    # 打开浏览器后不关闭
    options.add_experimental_option("detach", True)
    # 禁用Blink功能
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=options)
    # 覆盖window.navigate.webdriver
    # 打开浏览器后在控制台输入：window.navigator.webdriver    看返回是否是undefined-说明浏览器没有识别是selenium打开的浏览器、如果是true说明是被反爬了
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
        """
    })
    return driver


# 获取cookie
def get_cookie(index_url, login_url):
    driver = get_browser()
    driver.get(login_url)

    while True:
        time.sleep(5)
        while driver.current_url == index_url:

            # 获取登陆后的cookie信息
            # #返回一个列表字典-每个个字典中含有一个 name:value 键值对 、这个就是cookie的 名称和值
            tbCookies = driver.get_cookies()
            driver.quit()
            # print(tbCookies)
            print('==' * 60)
            # 遍历cookie
            cookies = {}
            for item in tbCookies:
                # 取出每个字典中的name和value 的值
                cookies[item['name']] = item['value']

            # 保存cookie
            output_path = open('../service/monitor/taobaoCookies.pickle', 'wb')
            # 将 Python 对象序列化保存到文件中
            # pickle.load(文件名) 反序列化、将文件内容反序列化为python对象
            pickle.dump(cookies, output_path)

            output_path.close()
            # print(cookies)
            return cookies


# 读取获取的cookie信息
def read_cookies(index_url, login_url):
    if os.path.exists('../service/monitor/taobaoCookies.pickle'):
        read_path = open('../service/monitor/taobaoCookies.pickle', 'rb')
        # pickle.load(read_path) 反序列化、将文件内容反序列化为 python对象
        tbCookies = pickle.load(read_path)
    else:
        tbCookies = get_cookie(index_url, login_url)

    return tbCookies


# 使用cookie去访问网页
def request_adress(index_url):
    tbCookies = read_cookies(index_url, login_url)
    driver = get_browser()
    driver.get(index_url)

    # 向当前浏览器会话中添加一个cookie
    for cookie in tbCookies:
        driver.add_cookie({
            "domain": ".taobao.com",  # 这是cookie的域名、域名前有一个 . 表示对所有的子域名都有效
            "name": cookie,  # cookie名称
            "value": tbCookies[cookie],  # cookie的值
            "path": '/',  # 这是cookie的路径。'/'表示该cookie对于域名的所有路径都是有效的
            "expires": None  # 这是cookie的过期时间。None表示该cookie没有过期时间，即它是一个会话cookie，当浏览器会话结束时它会被删除
        })

    # 再次请求网页-带cookie请求
    driver.get(index_url)

    print("登录后在这里针对淘宝做一些操作了。。。。。。。。。。。。")


if __name__ == '__main__':
    index_url = "https://www.taobao.com/"  # 淘宝首页
    login_url = "https://login.taobao.com/member/login.jhtml"  # 淘宝登录界面

    # 第一次登录要打开此函数用来获取cookie
    get_cookie(index_url, login_url)
    time.sleep(2)

    # 当获取cookie后打开这个函数去访问网页就不需要再登陆了
    request_adress("https://e.tb.cn/h.6hZQnmiX3g9Lar3?tk=xqUHVaFmXf5")