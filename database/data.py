#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@File data.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/4/16 1:05
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import decimal
import os

from loguru import logger
from config.read_yaml import read_conf_yaml
from database.mysql_util import MySQLUtil

curPath = os.path.abspath(os.path.dirname(__file__))
root = curPath[:curPath.find("TaobaoProductMonitor") + len("TaobaoProductMonitor")]

sysConf = read_conf_yaml(root + os.path.sep + 'config/web_config.yaml')


def query_monitor_products():
    """
    查询需要监控的产品
    :return: dict
    """
    mysql = MySQLUtil(sysConf['database']['host'], sysConf['database']['port'], sysConf['database']['user'],
                      sysConf['database']['pass'], sysConf['database']['db'])
    try:
        sql = """
        select *
        from store.products
        where monitor_status in (10,11)
        """
        logger.info("====================query_monitor_products Action")
        logger.info(sql)
        logger.info("====================query_monitor_products End")
        result = mysql.execute(sql)
        return result.fetchall()
    except Exception as e:
        logger.error(e)
        return None


def insert_products(platform: str, product_name: str, product_url: str, product_tk: str, notify_email: str):
    """
    产品表插入数据
    :param platform: 平台
    :param product_name: 产品名
    :param product_url: 产品链接
    :param product_tk: 产品tk
    :param notify_email: 通知邮箱地址
    :return: 产品id
    """
    mysql = MySQLUtil(sysConf['database']['host'], sysConf['database']['port'], sysConf['database']['user'],
                      sysConf['database']['pass'], sysConf['database']['db'])
    try:
        sql = """
        insert into store.products (
            user_id, platform, product_url, product_name, product_tk, notify_email
        )
        values (
            1, '%s', '%s', '%s', '%s', '%s'
        )
        """ % (platform, product_name, product_url, product_tk, notify_email)
        logger.info("====================insert_products Action")
        logger.info(sql)
        logger.info("====================insert_products End")
        result = mysql.execute(sql)
        if result.rowcount > 0:
            logger.info("数据插入成功，受影响行数，" + str(result.rowcount))
            return result.lastrowid
        else:
            logger.warning("数据插入失败")
            return None
    except Exception as e:
        logger.error(e)
        return None


def update_product_status(product_id: int, monitor_status: int):
    """
    更新产品的监控状态
    :param product_id: 产品id
    :param monitor_status: 监控状态
    :return:
    """
    mysql = MySQLUtil(sysConf['database']['host'], sysConf['database']['port'], sysConf['database']['user'],
                      sysConf['database']['pass'], sysConf['database']['db'])
    try:
        sql = """
        update store.products
        set monitor_status = %s
        where product_id = %s
        """ % (monitor_status, product_id)
        logger.info("====================update_product_status Action")
        logger.info(sql)
        logger.info("====================update_product_status End")
        result = mysql.execute(sql)
        if result.rowcount > 0:
            logger.info("数据插入成功，受影响行数，" + str(result.rowcount))
            return result.lastrowid
        else:
            logger.warning("数据插入失败")
            return None
    except Exception as e:
        logger.error(e)
        return None


def query_price_count(product_id: int):
    """
    通过产品id查询价格监控表条数
    :param product_id: 产品id
    :return: dict<数据条数>
    """
    mysql = MySQLUtil(sysConf['database']['host'], sysConf['database']['port'], sysConf['database']['user'],
                      sysConf['database']['pass'], sysConf['database']['db'])
    try:
        sql = """
        select count(*) as count
        from store.price_change
        where product_id = %s
        """ % product_id
        logger.info("====================query_price_count Action")
        logger.info(sql)
        logger.info("====================query_price_count End")
        result = mysql.execute(sql)
        for i in result:
            return i
    except Exception as e:
        logger.error(e)
        return None


def query_first_price(product_id: int):
    """
    根据产品id查询此产品最开始监控的价格
    :param product_id:
    :return: dict
    """
    mysql = MySQLUtil(sysConf['database']['host'], sysConf['database']['port'], sysConf['database']['user'],
                      sysConf['database']['pass'], sysConf['database']['db'])
    try:
        sql = """
        select *
        from store.price_change
        WHERE product_id = %s
        ORDER BY gmt_create
        limit 0,1
        """ % product_id
        logger.info("====================query_first_price Action")
        logger.info(sql)
        logger.info("====================query_first_price End")
        result = mysql.execute(sql)
        for i in result:
            return i
    except Exception as e:
        logger.error(e)
        return None


def insert_price(product_id: int, price: decimal):
    """
    价格监控表数据插入
    :param product_id: 产品id
    :param price: 价格
    :param notify_email: 通知邮箱地址
    :return: price_id
    """
    mysql = MySQLUtil(sysConf['database']['host'], sysConf['database']['port'], sysConf['database']['user'],
                      sysConf['database']['pass'], sysConf['database']['db'])
    try:
        sql = """
        insert into store.price_change(
        product_id, price
        )
        values (
        %s,'%s'
        )
        """ % (product_id, price)
        logger.info("====================insert_price Action")
        logger.info(sql)
        logger.info("====================insert_price End")
        result = mysql.execute(sql)
        if result.rowcount > 0:
            logger.info("数据插入成功，受影响行数，" + str(result.rowcount))
            return result.lastrowid
        else:
            logger.warning("数据插入失败")
            return None
    except Exception as e:
        logger.error(e)
        return None
