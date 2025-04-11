"""
@File read_conf.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/9/10 下午2:15
@Author Alan Huang
@Version 0.0.1
@Description None
"""
"""
@File read_conf.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/8/29 9:51
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import configparser
from config.manager_config import cm


class ReadConfig(object):
    """
    配置文件
    """
    def __init__(self):
        self.config = configparser.RawConfigParser()  # 当有%的符号时请使用Raw读取
        self.config.read(cm.ini_file, encoding='utf-8')

    def _get(self, section, option):
        """
        获取
        :param section:
        :param option:
        :return:
        """
        return self.config.get(section, option)

    def _set(self, section, option, value):
        """
        更新
        :param section:
        :param option:
        :param value:
        :return:
        """
        self.config.set(section, option, value)
        with open(cm.ini_file, 'w') as f:
            self.config.write(f)

    @property
    def taobao_cron(self):
        return self._get('taobao', 'cron')

    @property
    def mail_host(self):
        return self._get('mail', 'host')

    @property
    def mail_sender(self):
        return self._get('mail', 'sender')

    @property
    def mail_license(self):
        return self._get('mail', 'license')

    @property
    def log_tag(self):
        return self._get('log', 'tag')

    @property
    def log_save_path(self):
        return self._get('log', 'save_path')
