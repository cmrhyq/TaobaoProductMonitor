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

from loguru import logger

from dao.base_dao import BaseDao
from domain.entity.product import ProductInfo


class ProductDao(BaseDao):
    """
    产品数据访问对象
    """

    def __init__(self):
        super().__init__()

    def query_monitor_products(self) -> list:
        """
        查询需要监控的产品
        :return: dict
        """
        try:
            monitor_products = []
            logger.info("query_monitor_products Action")
            cursor = self.conn.cursor()
            sql = """
            select *
            from products
            where monitor_status in (10,11)
            """
            logger.info(sql)
            cursor.execute(sql)
            product_list = cursor.fetchall()
            for item in product_list:
                item_info = ProductInfo.from_dict(item)
                monitor_products.append(item_info)
            logger.info("query_monitor_products End")
            return monitor_products
        except Exception as e:
            logger.error(e)
            return []
        finally:
            self.conn.close()

    def insert_products(self, product: ProductInfo):
        """
        产品表插入数据
        :param product: 产品信息
        :return: 产品id
        """
        try:
            logger.info("insert_products Action")
            cursor = self.conn.cursor()
            sql = """
            insert into products (
                user_id, platform, product_url, product_name, product_tk, notify_email
            )
            values (
                1, '%s', '%s', '%s', '%s', '%s'
            )
            """ % (product.platform, product.product_url, product.product_name, product.product_tk, product.notify_email)

            logger.info(sql)
            result = cursor.execute(sql)

            logger.info("insert_products End")
            if result.rowcount > 0:
                self.conn.commit()
                logger.info("数据插入成功，受影响行数，" + str(result.rowcount))
                return result.lastrowid
            else:
                logger.warning("数据插入失败")
                return None
        except Exception as e:
            logger.error(e)
            return None
        finally:
            self.conn.close()

    def update_product_status(self, product: ProductInfo):
        """
        更新产品的监控状态
        :param product: ProductInfo
        :return:
        """
        try:
            logger.info("update_product_status Action")
            cursor = self.conn.cursor()
            sql = """
            update products
            set monitor_status = %s
            where product_id = %s
            """ % (product.monitor_status, product.product_id)
            logger.info(sql)
            result = cursor.execute(sql)
            logger.info("update_product_status End")
            if result.rowcount > 0:
                self.conn.commit()
                logger.info("数据插入成功，受影响行数，" + str(result.rowcount))
                return result.lastrowid
            else:
                logger.warning("数据插入失败")
                return None
        except Exception as e:
            logger.error(e)
            return None
        finally:
            self.conn.close()


if __name__ == '__main__':
    print(ProductDao().query_monitor_products())