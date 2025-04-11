import sqlite3

from config.manager_config import ManagerConfig


class BaseDao(object):
    """
    产品数据访问对象
    """

    def __init__(self):
        self.db_file = f"{ManagerConfig().BASE_DIR}\\db\\ProductMonitor.db"
        self.conn = sqlite3.connect(self.db_file)