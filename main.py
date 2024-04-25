from database.data import query_monitor_products
from monitor.taobao import get_product_price

dicts = query_monitor_products()
for i in dicts:
    get_product_price(i)
