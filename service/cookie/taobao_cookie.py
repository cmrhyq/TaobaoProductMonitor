import os
import pickle
import time
from contextlib import contextmanager
from loguru import logger
from common.selenium_service import SeleniumService
from domain.entity.selenium import SeleniumBase
from domain.enums.base_enums import SystemEnum


class TaobaoCookie(object):
    COOKIE_PICKLE_FILE = SystemEnum.PROJECT_BASE_PATH.name_value + os.path.sep + "\\resource\\cookie_pickle\\taobaoCookies.pickle"
    INDEX_URL = "https://www.taobao.com/"  # 淘宝首页
    LOGIN_URL = "https://login.taobao.com/member/login.jhtml"  # 淘宝登录界面

    def __init__(self):
        self.browser = None

    @contextmanager
    def _browser_context(self):
        """浏览器上下文管理器"""
        try:
            self.browser = SeleniumService()
            self.browser.start_browser(SeleniumBase(
                is_headless=False,
                is_cdp=True,
                is_dev=True,
                proxy="127.0.0.1:7890"
            ))
            yield self.browser
        finally:
            if self.browser:
                self.browser.close_browser()

    # 读取获取的cookie信息
    def read_cookies(self):
        if os.path.exists(self.COOKIE_PICKLE_FILE):
            read_path = open(self.COOKIE_PICKLE_FILE, 'rb')
            # pickle.load(read_path) 反序列化、将文件内容反序列化为 python对象
            tbCookies = pickle.load(read_path)
        else:
            tbCookies = self.get_cookie()

        return tbCookies

    def get_cookie(self):
        try:
            with self._browser_context() as browser:
                browser.start_page(self.LOGIN_URL)
                while True:
                    time.sleep(5)
                    while browser.current_url == self.INDEX_URL:
                        # 获取登陆后的cookie信息
                        # #返回一个列表字典-每个个字典中含有一个 name:value 键值对 、这个就是cookie的 名称和值
                        tbCookies = browser.get_cookies()
                        browser.quit()
                        # 遍历cookie
                        cookies = {}
                        for item in tbCookies:
                            # 取出每个字典中的name和value 的值
                            cookies[item['name']] = item['value']

                        # 保存cookie
                        output_path = open(self.COOKIE_PICKLE_FILE, 'wb')
                        # 将 Python 对象序列化保存到文件中
                        # pickle.load(文件名) 反序列化、将文件内容反序列化为python对象
                        pickle.dump(cookies, output_path)

                        output_path.close()
                        logger.info(cookies)
                        return cookies
        except Exception as e:
            logger.error(f"获取淘宝cookie失败，错误信息：{e}")


if __name__ == '__main__':
    taobao_cookie = TaobaoCookie()
    cookie = taobao_cookie.read_cookies()
    print(cookie)