-- TaobaoProductMonitor - SQLite 数据库初始化脚本 v2

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 商品表
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    platform TEXT NOT NULL DEFAULT '淘宝',
    product_url TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_tk TEXT,
    item_id TEXT,
    monitor_status INTEGER NOT NULL DEFAULT 10,
    notify_email TEXT NOT NULL,
    initial_price REAL,
    current_price REAL,
    lowest_price REAL,
    last_check_at DATETIME,
    check_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 价格历史表
CREATE TABLE IF NOT EXISTS price_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    price REAL NOT NULL,
    original_price REAL,
    fetch_method TEXT NOT NULL DEFAULT 'api',
    is_valid INTEGER NOT NULL DEFAULT 1,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 监控规则表
CREATE TABLE IF NOT EXISTS monitor_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    rule_type TEXT NOT NULL DEFAULT 'absolute_drop',
    threshold_value REAL,
    threshold_percent REAL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 通知记录表
CREATE TABLE IF NOT EXISTS notification_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    rule_id INTEGER,
    notify_type TEXT NOT NULL DEFAULT 'email',
    notify_target TEXT NOT NULL,
    notify_content TEXT,
    notify_status INTEGER NOT NULL DEFAULT 1,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (rule_id) REFERENCES monitor_rules(rule_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_monitor_status ON products(monitor_status);
CREATE INDEX IF NOT EXISTS idx_products_item_id ON products(item_id);
CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded_at ON price_history(recorded_at);
CREATE INDEX IF NOT EXISTS idx_monitor_rules_product_id ON monitor_rules(product_id);
CREATE INDEX IF NOT EXISTS idx_notification_log_product_id ON notification_log(product_id);

-- 插入默认用户
INSERT OR IGNORE INTO users (user_id, username, email) VALUES (1, 'default', 'cmrhyq@163.com');

-- 插入示例数据
INSERT OR IGNORE INTO products (product_id, user_id, platform, product_url, product_name, product_tk, monitor_status, notify_email, created_at, updated_at)
VALUES
    (19, 1, '淘宝', 'https://m.tb.cn/h.5zxyK10h65Gy9AU?tk=X2X2WKIqj7', '优衣库女装麻混纺吊带连衣裙(打褶高腰时尚法式轻盈新款)466540', 'X2X2WKIqj7o', 11, 'cmrhyq@163.com', '2024-04-18 00:43:20', '2024-04-25 21:18:06'),
    (20, 1, '淘宝', 'https://m.tb.cn/h.5zxz3j69cN5go4k?tk=XUymWKIqxIz', '优衣库女装网眼V领短针织开衫长袖薄外套空调衫2024新款468541', 'XUymWKIqxIz', 11, 'cmrhyq@163.com', '2024-04-18 00:43:20', '2024-04-25 21:18:06');

-- 为示例数据插入默认监控规则（降价任意金额通知）
INSERT OR IGNORE INTO monitor_rules (rule_id, product_id, rule_type, threshold_value, is_active)
VALUES
    (1, 19, 'absolute_drop', 0.01, 1),
    (2, 20, 'absolute_drop', 0.01, 1);
