-- TaobaoProductMonitor - SQLite 数据库初始化脚本
--
-- ⚠️ 仅供**全新数据库**使用：脚本末尾含示例商品数据（products / monitor_rules 各 2 条），
--    在已有真实数据的库上执行会污染数据。
--    存量库升级请改用 db/migration_v4.sql；服务启动时 init_db() 会自动 create_all 建表。
--
-- 字段含义以行尾 `--` 注释给出（SQLite 不支持列级 COMMENT 关键字）。
-- 枚举取值与 data/models.py、data/repository/ 保持一致，改代码时请同步维护本文件。

-- 用户表：监控商品的所有者。当前业务固定使用 user_id = 1
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,      -- 用户主键，自增
    username TEXT NOT NULL,                         -- 用户名
    email TEXT NOT NULL,                            -- 邮箱
    phone TEXT,                                     -- 手机号，可空
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP   -- 最后更新时间（本脚本不自动更新，由应用层维护）
);

-- 商品表：待监控 / 在监控的商品，同时缓存最新价格快照供列表展示
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 商品主键，自增
    user_id INTEGER NOT NULL,                       -- 所属用户，外键 users.user_id
    platform TEXT NOT NULL DEFAULT '淘宝',          -- 平台名，取自分享文本如「【淘宝】」
    product_url TEXT NOT NULL,                      -- 商品完整链接（已规范化，非短链）
    product_name TEXT NOT NULL,                     -- 商品标题；分享文本缺标题时兜底为「淘宝商品 {item_id}」
    product_tk TEXT,                                -- 分享链接的 tk 参数（淘宝分享签名参数）
    item_id TEXT,                                   -- 淘宝商品数字 ID，抓取时解析并回写（短链改版后仍能重新解析）
    monitor_status INTEGER NOT NULL DEFAULT 10,     -- 监控状态：10=未开始 11=监控中 12=已结束
    notify_email TEXT NOT NULL,                     -- 降价通知收件邮箱
    initial_price REAL,                             -- 首次监控价，作为降价判定基准
    current_price REAL,                             -- 最近一次抓取的实付价（优惠后）
    lowest_price REAL,                              -- 历史最低实付价
    last_check_at DATETIME,                         -- 最近一次抓取时间
    check_count INTEGER NOT NULL DEFAULT 0,         -- 累计抓取成功次数
    fail_count INTEGER NOT NULL DEFAULT 0,          -- 累计抓取失败次数
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 最后更新时间（由应用层显式更新）
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 价格历史表：窄时间序列，每次成功抓取追加一行
-- 富数据（标题 / SKU / 参数 / 店铺 / 图片）不在这里，见 product_snapshot
CREATE TABLE IF NOT EXISTS price_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键，自增
    product_id INTEGER NOT NULL,                     -- 所属商品，外键 products.product_id
    price REAL NOT NULL,                             -- 本次实付价（店铺优惠后）
    original_price REAL,                             -- 优惠前价 / 划线价，仅检测到促销时记录
    fetch_method TEXT NOT NULL DEFAULT 'api',        -- 数据来源：ssr-pc / mtop-page / dom-page / mtop-http（DEFAULT 为历史遗留值，代码总是显式传值）
    is_valid INTEGER NOT NULL DEFAULT 1,             -- 1=有效 0=无效；当前代码只读不写，恒为 1（预留作无效价过滤）
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 记录时间
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 监控规则表：一个商品可挂多条规则，任一条命中即通知
CREATE TABLE IF NOT EXISTS monitor_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,        -- 主键，自增
    product_id INTEGER NOT NULL,                      -- 所属商品，外键 products.product_id
    rule_type TEXT NOT NULL DEFAULT 'absolute_drop',  -- 规则类型：absolute_drop / percent_drop / target_price
    threshold_value REAL,                             -- 绝对降额（元）或目标价，含义随 rule_type 变化
    threshold_percent REAL,                           -- 百分比降幅阈值（%），仅 percent_drop 使用
    is_active INTEGER NOT NULL DEFAULT 1,             -- 是否启用：1=启用 0=停用
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,    -- 创建时间
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 通知记录表：每次触发通知留痕（成功与失败都记）
CREATE TABLE IF NOT EXISTS notification_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主键，自增
    product_id INTEGER NOT NULL,                 -- 所属商品，外键 products.product_id
    rule_id INTEGER,                             -- 命中的规则，外键 monitor_rules.rule_id，可空
    notify_type TEXT NOT NULL DEFAULT 'email',   -- 通知渠道，当前仅 email
    notify_target TEXT NOT NULL,                 -- 通知目标（收件邮箱）
    notify_content TEXT,                         -- 通知内容摘要；发送失败时记录错误信息
    notify_status INTEGER NOT NULL DEFAULT 1,    -- 通知结果：1=成功 0=失败
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 发送时间
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (rule_id) REFERENCES monitor_rules(rule_id)
);

-- 商品快照表：每次成功抓取追加一行，存该次抓取的完整商品信息
-- price_history 只管价格时序（窄），本表存全部字段（宽），两者按需要分开查询
-- 价格语义：price_current 为实付价（优惠后），price_original 为优惠前价
CREATE TABLE IF NOT EXISTS product_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 主键，自增
    product_id INTEGER NOT NULL,                    -- 所属商品，外键 products.product_id
    item_id TEXT,                                   -- 淘宝商品 ID
    title TEXT,                                     -- 商品标题
    subtitle TEXT,                                  -- 副标题 / 卖点
    price_current REAL,                             -- 实付价（优惠后）
    price_original REAL,                            -- 优惠前价 / 划线价
    price_low REAL,                                 -- 多 SKU 区间最低价（无统一实付价时使用）
    price_high REAL,                                -- 多 SKU 区间最高价
    price_text TEXT,                                -- 页面上的价格原文
    promotions_json TEXT,                           -- 促销信息，JSON 数组
    stock_total INTEGER,                            -- 各 SKU 库存合计
    sold_text TEXT,                                 -- 已售文案原文（如「已售 4」）
    skus_json TEXT,                                 -- SKU 列表，JSON 数组（规格组合 / 各规格价 / 库存）
    attributes_json TEXT,                           -- 商品参数，JSON 数组（键值对）
    images_json TEXT,                               -- 主图 URL，JSON 数组
    shop_json TEXT,                                 -- 店铺信息，JSON 对象
    shop_name TEXT,                                 -- 店铺名（从 shop_json 冗余出来，便于列表直接展示）
    source TEXT,                                    -- 数据来源：ssr-pc / mtop-page / dom-page
    fetched_at DATETIME,                            -- 抓取完成时间（数据本身的采集时刻）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 落库时间
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 索引：覆盖按用户 / 状态 / 商品 ID 的单表查询，以及按商品与时间的时间序列查询
CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_monitor_status ON products(monitor_status); -- 筛选待监控商品
CREATE INDEX IF NOT EXISTS idx_products_item_id ON products(item_id);
CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded_at ON price_history(recorded_at); -- 价格趋势按时间排序
CREATE INDEX IF NOT EXISTS idx_monitor_rules_product_id ON monitor_rules(product_id);
CREATE INDEX IF NOT EXISTS idx_notification_log_product_id ON notification_log(product_id);
CREATE INDEX IF NOT EXISTS idx_product_snapshot_product_id ON product_snapshot(product_id);
CREATE INDEX IF NOT EXISTS idx_product_snapshot_fetched_at ON product_snapshot(fetched_at); -- 取最近一次快照
CREATE INDEX IF NOT EXISTS idx_product_snapshot_item_id ON product_snapshot(item_id);

-- 插入默认用户
INSERT OR IGNORE INTO users (user_id, username, email) VALUES (1, 'default', 'cmrhyq@163.com');

-- 插入示例数据（⚠️ 仅供全新库演示，勿在真实库执行）
INSERT OR IGNORE INTO products (product_id, user_id, platform, product_url, product_name, product_tk, monitor_status, notify_email, created_at, updated_at)
VALUES
    (19, 1, '淘宝', 'https://m.tb.cn/h.5zxyK10h65Gy9AU?tk=X2X2WKIqj7', '优衣库女装麻混纺吊带连衣裙(打褶高腰时尚法式轻盈新款)466540', 'X2X2WKIqj7o', 11, 'cmrhyq@163.com', '2024-04-18 00:43:20', '2024-04-25 21:18:06'),
    (20, 1, '淘宝', 'https://m.tb.cn/h.5zxz3j69cN5go4k?tk=XUymWKIqxIz', '优衣库女装网眼V领短针织开衫长袖薄外套空调衫2024新款468541', 'XUymWKIqxIz', 11, 'cmrhyq@163.com', '2024-04-18 00:43:20', '2024-04-25 21:18:06');

-- 为示例数据插入默认监控规则（降价任意金额即通知）
INSERT OR IGNORE INTO monitor_rules (rule_id, product_id, rule_type, threshold_value, is_active)
VALUES
    (1, 19, 'absolute_drop', 0.01, 1),
    (2, 20, 'absolute_drop', 0.01, 1);
