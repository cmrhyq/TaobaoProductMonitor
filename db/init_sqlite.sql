-- 创建数据库（如果不存在）
-- SQLite 会自动创建数据库文件，无需显式创建

-- 创建表
create table if not exists `price_monitor` (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT, -- 价格id
    product_id INTEGER, -- 产品表id
    price REAL, -- 第一次的价格
    gmt_create DATETIME DEFAULT CURRENT_TIMESTAMP, -- 创建时间
    gmt_modified DATETIME DEFAULT CURRENT_TIMESTAMP -- 更新时间
);

create table if not exists `products` (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 产品id
    user_id INTEGER, -- 用户id
    platform TEXT,  -- 平台
    product_url TEXT,  -- 商品链接
    product_name TEXT,  -- 商品名称
    product_tk TEXT,  -- 商品url中的tk
    monitor_status INTEGER DEFAULT 10,  -- 监控状态（10=未开始, 11=监控中, 12=已结束）
    notify_email TEXT,  -- 接收通知的邮件地址
    gmt_create DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    gmt_modified DATETIME DEFAULT CURRENT_TIMESTAMP  -- 更新时间
);

-- 插入一些初始数据（可选）
insert into products (product_id, user_id, platform, product_url, product_name, product_tk, monitor_status, notify_email, gmt_create, gmt_modified)
values  (19, 1, '淘宝', 'https://m.tb.cn/h.5zxyK10h65Gy9AU?tk=X2X2WKIqj7', '优衣库女装麻混纺吊带连衣裙(打褶高腰时尚法式轻盈新款)466540', 'X2X2WKIqj7o ', 11, 'cmrhyq@163.com', '2024-04-18 00:43:20', '2024-04-25 21:18:06'),
        (20, 1, '淘宝', 'https://m.tb.cn/h.5zxz3j69cN5go4k?tk=XUymWKIqxIz', '优衣库女装网眼V领短针织开衫长袖薄外套空调衫2024新款468541', 'XUymWKIqxIz', 11, 'cmrhyq@163.com', '2024-04-18 00:43:20', '2024-04-25 21:18:06');