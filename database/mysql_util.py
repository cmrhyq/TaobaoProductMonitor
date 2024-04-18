#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@File mysql_util.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/4/15 23:56
@Author Alan Huang
@Version 0.0.1
@Description None
"""
import pymysql


class MySQLUtil:
    """
    MySQL工具类
    """

    def __init__(self, host="127.0.0.1", port=3306, user=None, passwd=None, db=None, charset="utf8", *args, **kwargs):
        """
        构造函数
        :param host:
        :param user:
        :param passwd:
        :param db:
        :param charset:
        :param args:
        :param kwargs:
        """
        self.__host = host
        self.__user = user
        self.__passwd = passwd
        self.__db = db
        self.__conn = pymysql.connect(host=host, port=port, user=user, passwd=passwd, db=db, charset=charset, *args,
                                      **kwargs)
        self.__cursor = self.__conn.cursor(cursor=pymysql.cursors.DictCursor)

    def __del__(self):
        """
        析构函数
        :return:
        """
        self.__cursor.close()
        self.__conn.close()

    def get_conn(self):
        """
        获取连接
        :return:
        """
        return self.__conn

    def get_cursor(self, cursor=None):
        """
        获取游标
        :param cursor:
        :return:
        """
        return self.__conn.cursor(cursor)

    def select_db(self, db):
        """
        选择数据库
        :param db:
        :return:
        """
        self.__conn.select_db(db)

    def list_databases(self, args=None):
        """
        查询所有数据库
        :param args:
        :return:
        """
        self.__cursor.execute("SHOW DATABASES", args)
        dbs = []
        for db in self.__cursor.fetchall():
            dbs.append(db[0])
        return dbs

    def list_tables(self, args=None):
        """
        查询所有表
        :param args:
        :return:
        """
        self.__cursor.execute("SHOW TABLES", args)
        tables = []
        for table in self.__cursor.fetchall():
            tables.append(table[0])
        return tables

    def execute(self, sql, args=None):
        """
        获取SQL执行结果
        :param sql:
        :param args:
        :return:
        """
        self.__cursor.execute(sql, args)
        self.__conn.commit()
        return self.__cursor

    def get_version(self, args=None):
        """
        获取MySQL版本
        :param args:
        :return:
        """
        self.__cursor.execute("SELECT VERSION()", args)
        version = self.__cursor.fetchone()
        print("MySQL Version : %s" % version)
        return version

    def list_table_metadata(self, args=None):
        """
        查询所有表的元数据信息
        :param args:
        :return:
        """
        sql = ("SELECT * FROM information_schema.TABLES WHERE TABLE_TYPE !='SYSTEM VIEW' AND TABLE_SCHEMA NOT IN ("
               "'sys','mysql','information_schema','performance_schema')")
        self.__cursor.execute(sql, args)
        return self.__cursor.fetchall()

    def get_table_fields(self, db, table, args=None):
        """
        获取表字段信息
        :param db:
        :param table:
        :param args:
        :return:
        """
        sql = 'SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE table_schema="' + db + '" AND table_name="' + table + '"'
        self.__cursor.execute(sql, args)
        fields = []
        for field in self.__cursor.fetchall():
            fields.append(field[0])
        return fields

    def table_metadata(self, db, table, args=None):
        """
        查询表字段的元数据信息
        :param db:
        :param table:
        :param args:
        :return:
        """
        db = "'" + db + "'"
        table = "'" + table + "'"
        sql = """
        SELECT 
            column_name,column_type,ordinal_position,column_comment,column_default 
        FROM 
            information_schema.COLUMNS 
        WHERE 
            table_schema = %s AND table_name = %s;
        """ % (db, table)
        self.__cursor.execute(sql, args)
        return self.__cursor.fetchall()


if __name__ == "__main__":
    mysqlUtil = MySQLUtil("127.0.0.1", 3306, "root", "Hyq0901.", "store")
    # mysqlUtil = MySQLUtil(host="127.0.0.1", user="root", passwd="Hyq0901.", db="store")
    mysqlUtil.get_version()
    dbs = mysqlUtil.list_databases()
    print(dbs)
    conn = mysqlUtil.get_conn()
    mysqlUtil.select_db("store")
    print(type(conn.db), conn.db)
    databases = mysqlUtil.list_databases()
    print(type(databases), databases)
    tables = mysqlUtil.list_tables()
    print(type(tables), tables)
    sql = "SELECT * FROM store.user"
    result = mysqlUtil.execute(sql)
    for i in result:
        print(i)
    result = mysqlUtil.table_metadata("test", "t_user")
    result = mysqlUtil.get_table_fields("test", "t_user")
    for i in result:
        print(i)
