import os
import schedule
import time
from datetime import datetime

from loguru import logger

from config.read_yaml import read_conf_yaml
from task.task import product_monitor_task

curPath = os.path.abspath(os.path.dirname(__file__))
root = curPath[:curPath.find("TaobaoProductMonitor") + len("TaobaoProductMonitor")]
sysConf = read_conf_yaml(root + os.path.sep + 'config/web_config.yaml')
logger.add(sysConf["log"]["filename"])


def job():
    logger.info("任务开始执行，{}".format(datetime.now()))
    product_monitor_task()
    logger.info("任务执行结束，{}".format(datetime.now()))


# 定义每周二、四的上午六点和下午八点执行任务
schedule.every().tuesday.at("06:00").do(job)
schedule.every().tuesday.at("20:00").do(job)
schedule.every().thursday.at("06:00").do(job)
schedule.every().thursday.at("20:00").do(job)
schedule.every().friday.at("01:01").do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
