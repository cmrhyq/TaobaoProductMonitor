#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@File product_dao.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/4/16 1:05
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import decimal

from loguru import logger

from dao.base_dao import BaseDao
from domain.entity.price import Price


class PriceMonitorDao(BaseDao):
    """
    产品数据访问对象
    """

    def __init__(self):
        super().__init__()

    def query_price_count(self, product_id: int):
        """
        通过产品id查询价格监控表条数
        :param product_id: 产品id
        :return: dict<数据条数>
        """
        try:
            logger.info("====================query_price_count Action")
            cursor = self.conn.cursor()
            sql = """
            select count(*) as count
            from price_change
            where product_id = %s
            """ % product_id
            logger.info(sql)
            result = cursor.execute(sql)
            logger.info("====================query_price_count End")
            for i in result:
                return i
        except Exception as e:
            logger.error(e)
            return None

    def query_first_price(self, product_id: int):
        """
        根据产品id查询此产品最开始监控的价格
        :param product_id:
        :return: dict
        """
        try:
            logger.info("====================query_first_price Action")
            cursor = self.conn.cursor()
            sql = """
            select *
            from price_change
            WHERE product_id = %s
            ORDER BY gmt_create
            limit 0,1
            """ % product_id
            logger.info(sql)
            result = cursor.execute(sql)
            logger.info("====================query_first_price End")
            for i in result:
                return i
        except Exception as e:
            logger.error(e)
            return None

    def insert_price(self, price_info: Price):
        """
        价格监控表数据插入
        :param price_info: 价格信息
        :return: price_id
        """
        try:
            logger.info("====================insert_price Action")
            cursor = self.conn.cursor()
            sql = """
            insert into price_change(
                product_id, price
            )
            values (
            %s,'%s'
            )
            """ % (price_info.product_id, price_info.price)
            logger.info(sql)
            result = cursor.execute(sql)
            logger.info("====================insert_price End")
            if result.rowcount > 0:
                logger.info("数据插入成功，受影响行数，" + str(result.rowcount))
                return result.lastrowid
            else:
                logger.warning("数据插入失败")
                return None
        except Exception as e:
            logger.error(e)
            return None




