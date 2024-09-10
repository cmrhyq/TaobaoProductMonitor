import os
import schedule
import time
from datetime import datetime

from loguru import logger

from common.logging_log import MyLogger
from common.read_conf import ReadConfig
from task.task import product_monitor_task

rc = ReadConfig()
log = MyLogger(tag=rc.log_tag, colorful=True, save_pth=rc.log_save_path, existing_counts=rc.log_exist_counts)


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
