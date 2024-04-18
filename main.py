# import os
# from datetime import datetime
#
# import schedule
# import time
#
# from loguru import logger
# from config.read_yaml import read_conf_yaml
# from database.data import query_monitor_products
# from monitor.taobao import get_product_price
#
# curPath = os.path.abspath(os.path.dirname(__file__))
# root = curPath[:curPath.find("TaobaoProductMonitor") + len("TaobaoProductMonitor")]
# sysConf = read_conf_yaml(root + os.path.sep + 'config/web_config.yaml')
# logger.add(sysConf['log']['filename'])
#
#
# def job():
#     logger.info("产品监控定时任务开始执行，执行时间：%s" % datetime.now())
#     dicts = query_monitor_products()
#     for i in dicts:
#         get_product_price(i)
#     logger.info("产品监控定时任务执行完成")
#
#
# # 每周二上午6点执行
# schedule.every().tuesday.at("06:00").do(job)
#
# # 每周二下午8点执行
# schedule.every().tuesday.at("20:00").do(job)
#
# # 每周四上午6点执行
# schedule.every().thursday.at("06:00").do(job)
#
# # 每周四下午8点执行
# schedule.every().thursday.at("20:00").do(job)
#
# while True:
#     schedule.run_pending()
#     time.sleep(1)
from database.data import query_monitor_products
from monitor.taobao import get_product_price

dicts = query_monitor_products()
for i in dicts:
    get_product_price(i)