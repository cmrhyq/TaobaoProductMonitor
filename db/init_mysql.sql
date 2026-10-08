-- TaobaoProductMonitor - MySQL 数据库初始化脚本
--
-- ⚠️ 仅供**全新数据库**使用：脚本末尾会插入默认用户（user_id = 1）。
--    存量库升级请改用 db/migration_v4.sql；服务启动时 init_db() 会自动 create_all 建表。
--
-- 字段含义用 MySQL 原生列注释 COMMENT 给出，可用
--   SHOW FULL COLUMNS FROM <表名>;
-- 查看。枚举取值与 data/models.py、data/repository/ 保持一致，改代码时请同步维护本文件。

CREATE DATABASE IF NOT EXISTS product_monitor DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE product_monitor;

-- 用户表：监控商品的所有者。当前业务固定使用 user_id = 1
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户主键，自增',
    username VARCHAR(64) NOT NULL COMMENT '用户名',
    email VARCHAR(128) NOT NULL COMMENT '邮箱',
    phone VARCHAR(20) COMMENT '手机号，可空',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（数据库自动维护）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 商品表：待监控 / 在监控的商品，同时缓存最新价格快照供列表展示
CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '商品主键，自增',
    user_id INT NOT NULL COMMENT '所属用户，外键 users.user_id',
    platform VARCHAR(32) NOT NULL DEFAULT '淘宝' COMMENT '平台名，取自分享文本如【淘宝】',
    product_url TEXT NOT NULL COMMENT '商品完整链接（已规范化，非短链）',
    product_name VARCHAR(512) NOT NULL COMMENT '商品标题；分享文本缺标题时兜底为「淘宝商品 {item_id}」',
    product_tk VARCHAR(64) COMMENT '分享链接的 tk 参数（淘宝分享签名参数）',
    item_id VARCHAR(32) COMMENT '淘宝商品数字 ID，抓取时解析并回写',
    monitor_status INT NOT NULL DEFAULT 10 COMMENT '监控状态：10=未开始 11=监控中 12=已结束',
    notify_email VARCHAR(128) NOT NULL COMMENT '降价通知收件邮箱',
    initial_price DECIMAL(10, 2) COMMENT '首次监控价，作为降价判定基准',
    current_price DECIMAL(10, 2) COMMENT '最近一次抓取的实付价（优惠后）',
    lowest_price DECIMAL(10, 2) COMMENT '历史最低实付价',
    last_check_at DATETIME COMMENT '最近一次抓取时间',
    check_count INT NOT NULL DEFAULT 0 COMMENT '累计抓取成功次数',
    fail_count INT NOT NULL DEFAULT 0 COMMENT '累计抓取失败次数',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间（数据库自动维护）',
    INDEX idx_user_id (user_id),
    INDEX idx_monitor_status (monitor_status) COMMENT '筛选待监控商品',
    INDEX idx_item_id (item_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- 价格历史表：窄时间序列，每次成功抓取追加一行
-- 富数据（标题 / SKU / 参数 / 店铺 / 图片）不在这里，见 product_snapshot
CREATE TABLE IF NOT EXISTS price_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键，自增',
    product_id INT NOT NULL COMMENT '所属商品，外键 products.product_id',
    price DECIMAL(10, 2) NOT NULL COMMENT '本次实付价（店铺优惠后）',
    original_price DECIMAL(10, 2) COMMENT '优惠前价 / 划线价，仅检测到促销时记录',
    fetch_method VARCHAR(32) NOT NULL DEFAULT 'api' COMMENT '数据来源：ssr-pc / mtop-page / dom-page / mtop-http（DEFAULT 为历史遗留值，代码总是显式传值）',
    is_valid TINYINT NOT NULL DEFAULT 1 COMMENT '1=有效 0=无效；当前代码只读不写，恒为 1（预留作无效价过滤）',
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    INDEX idx_product_id (product_id),
    INDEX idx_recorded_at (recorded_at) COMMENT '价格趋势按时间排序',
    FOREIGN KEY (product_id) REFERENCES products(product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='价格历史表（窄时间序列）';

-- 监控规则表：一个商品可挂多条规则，任一条命中即通知
CREATE TABLE IF NOT EXISTS monitor_rules (
    rule_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键，自增',
    product_id INT NOT NULL COMMENT '所属商品，外键 products.product_id',
    rule_type VARCHAR(32) NOT NULL DEFAULT 'absolute_drop' COMMENT '规则类型：absolute_drop / percent_drop / target_price',
    threshold_value DECIMAL(10, 2) COMMENT '绝对降额（元）或目标价，含义随 rule_type 变化',
    threshold_percent DECIMAL(5, 2) COMMENT '百分比降幅阈值（%），仅 percent_drop 使用',
    is_active TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用：1=启用 0=停用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_product_id (product_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='监控规则表';

-- 通知记录表：每次触发通知留痕（成功与失败都记）
CREATE TABLE IF NOT EXISTS notification_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键，自增',
    product_id INT NOT NULL COMMENT '所属商品，外键 products.product_id',
    rule_id INT COMMENT '命中的规则，外键 monitor_rules.rule_id，可空',
    notify_type VARCHAR(32) NOT NULL DEFAULT 'email' COMMENT '通知渠道，当前仅 email',
    notify_target VARCHAR(256) NOT NULL COMMENT '通知目标（收件邮箱）',
    notify_content TEXT COMMENT '通知内容摘要；发送失败时记录错误信息',
    notify_status TINYINT NOT NULL DEFAULT 1 COMMENT '通知结果：1=成功 0=失败',
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '发送时间',
    INDEX idx_product_id (product_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (rule_id) REFERENCES monitor_rules(rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通知记录表';

-- 商品快照表：每次成功抓取追加一行，存该次抓取的完整商品信息
-- price_history 只管价格时序（窄），本表存全部字段（宽），两者按需要分开查询
-- 价格语义：price_current 为实付价（优惠后），price_original 为优惠前价
CREATE TABLE IF NOT EXISTS product_snapshot (
    snapshot_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键，自增',
    product_id INT NOT NULL COMMENT '所属商品，外键 products.product_id',
    item_id VARCHAR(100) COMMENT '淘宝商品 ID',
    title VARCHAR(500) COMMENT '商品标题',
    subtitle TEXT COMMENT '副标题 / 卖点',
    price_current DECIMAL(10, 2) COMMENT '实付价（优惠后）',
    price_original DECIMAL(10, 2) COMMENT '优惠前价 / 划线价',
    price_low DECIMAL(10, 2) COMMENT '多 SKU 区间最低价（无统一实付价时使用）',
    price_high DECIMAL(10, 2) COMMENT '多 SKU 区间最高价',
    price_text VARCHAR(200) COMMENT '页面上的价格原文',
    promotions_json LONGTEXT COMMENT '促销信息，JSON 数组',
    stock_total INT COMMENT '各 SKU 库存合计',
    sold_text VARCHAR(100) COMMENT '已售文案原文（如：已售 4）',
    skus_json LONGTEXT COMMENT 'SKU 列表，JSON 数组（规格组合 / 各规格价 / 库存）',
    attributes_json LONGTEXT COMMENT '商品参数，JSON 数组（键值对）',
    images_json LONGTEXT COMMENT '主图 URL，JSON 数组',
    shop_json LONGTEXT COMMENT '店铺信息，JSON 对象',
    shop_name VARCHAR(200) COMMENT '店铺名（从 shop_json 冗余，便于列表展示）',
    source VARCHAR(50) COMMENT '数据来源：ssr-pc / mtop-page / dom-page',
    fetched_at DATETIME COMMENT '抓取完成时间（数据本身的采集时刻）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '落库时间',
    INDEX idx_product_id (product_id),
    INDEX idx_fetched_at (fetched_at) COMMENT '取最近一次快照',
    INDEX idx_item_id (item_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品快照表（宽数据）';

-- 插入默认用户
INSERT IGNORE INTO users (user_id, username, email) VALUES (1, 'default', 'cmrhyq@163.com');
