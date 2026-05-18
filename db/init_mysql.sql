-- TaobaoProductMonitor - MySQL 数据库初始化脚本 v2

CREATE DATABASE IF NOT EXISTS product_monitor DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE product_monitor;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    email VARCHAR(128) NOT NULL,
    phone VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 商品表
CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    platform VARCHAR(32) NOT NULL DEFAULT '淘宝',
    product_url TEXT NOT NULL,
    product_name VARCHAR(512) NOT NULL,
    product_tk VARCHAR(64),
    item_id VARCHAR(32),
    monitor_status INT NOT NULL DEFAULT 10 COMMENT '10=未开始, 11=监控中, 12=已结束',
    notify_email VARCHAR(128) NOT NULL,
    initial_price DECIMAL(10, 2),
    current_price DECIMAL(10, 2),
    lowest_price DECIMAL(10, 2),
    last_check_at DATETIME,
    check_count INT NOT NULL DEFAULT 0,
    fail_count INT NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_monitor_status (monitor_status),
    INDEX idx_item_id (item_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 价格历史表
CREATE TABLE IF NOT EXISTS price_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    fetch_method VARCHAR(32) NOT NULL DEFAULT 'api' COMMENT 'api/playwright/selenium',
    is_valid TINYINT NOT NULL DEFAULT 1,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product_id (product_id),
    INDEX idx_recorded_at (recorded_at),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 监控规则表
CREATE TABLE IF NOT EXISTS monitor_rules (
    rule_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    rule_type VARCHAR(32) NOT NULL DEFAULT 'absolute_drop' COMMENT 'absolute_drop/percent_drop/target_price',
    threshold_value DECIMAL(10, 2) COMMENT '绝对降价阈值或目标价格',
    threshold_percent DECIMAL(5, 2) COMMENT '百分比降价阈值',
    is_active TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product_id (product_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 通知记录表
CREATE TABLE IF NOT EXISTS notification_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    rule_id INT,
    notify_type VARCHAR(32) NOT NULL DEFAULT 'email',
    notify_target VARCHAR(256) NOT NULL,
    notify_content TEXT,
    notify_status TINYINT NOT NULL DEFAULT 1 COMMENT '1=成功, 0=失败',
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product_id (product_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (rule_id) REFERENCES monitor_rules(rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 插入默认用户
INSERT IGNORE INTO users (user_id, username, email) VALUES (1, 'default', 'cmrhyq@163.com');
