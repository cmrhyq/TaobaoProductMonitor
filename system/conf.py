"""
@File conf.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/9/10 下午2:16
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import os
import sys

from utils.time_utils import dt_strftime


class ConfigManager(object):
    # idea中的项目目录
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 打包后的项目目录 , "."
    # BASE_DIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])))

    @property
    def log_file(self):
        """日志目录"""
        log_dir = os.path.join(self.BASE_DIR, 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        return os.path.join(log_dir, '{}.logs'.format(dt_strftime()))

    @property
    def ini_file(self):
        """
        配置文件
        :return:
        """
        ini_file = os.path.join(self.BASE_DIR, 'resource', 'common.ini')
        if not os.path.exists(ini_file):
            raise FileNotFoundError("配置文件%s不存在！" % ini_file)
        return ini_file


cm = ConfigManager()
if __name__ == '__main__':
    print(cm.ini_file)
