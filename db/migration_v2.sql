-- Migration from v1 to v2
-- Run this if you have existing data in the old schema

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO users (user_id, username, email)
SELECT DISTINCT user_id, 'user_' || user_id, notify_email
FROM products;

-- Add new columns to products
ALTER TABLE products ADD COLUMN item_id TEXT;
ALTER TABLE products ADD COLUMN initial_price REAL;
ALTER TABLE products ADD COLUMN current_price REAL;
ALTER TABLE products ADD COLUMN lowest_price REAL;
ALTER TABLE products ADD COLUMN last_check_at DATETIME;
ALTER TABLE products ADD COLUMN check_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE products ADD COLUMN fail_count INTEGER NOT NULL DEFAULT 0;

-- Rename old price table to new structure
CREATE TABLE IF NOT EXISTS price_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    price REAL NOT NULL,
    fetch_method TEXT NOT NULL DEFAULT 'selenium',
    is_valid INTEGER NOT NULL DEFAULT 1,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- Migrate old price data
INSERT INTO price_history (product_id, price, fetch_method, recorded_at)
SELECT product_id, price, 'selenium', gmt_create
FROM price_change;

-- Create monitor_rules table
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

-- Create default rules for existing products
INSERT INTO monitor_rules (product_id, rule_type, threshold_value, is_active)
SELECT product_id, 'absolute_drop', 0.01, 1
FROM products
WHERE monitor_status IN (10, 11);

-- Create notification_log table
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

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_monitor_status ON products(monitor_status);
CREATE INDEX IF NOT EXISTS idx_products_item_id ON products(item_id);
CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded_at ON price_history(recorded_at);
CREATE INDEX IF NOT EXISTS idx_monitor_rules_product_id ON monitor_rules(product_id);
CREATE INDEX IF NOT EXISTS idx_notification_log_product_id ON notification_log(product_id);

-- Update initial_price from first recorded price
UPDATE products SET initial_price = (
    SELECT MIN(price) FROM price_history ph WHERE ph.product_id = products.product_id
);
UPDATE products SET current_price = (
    SELECT price FROM price_history ph WHERE ph.product_id = products.product_id ORDER BY recorded_at DESC LIMIT 1
);
UPDATE products SET lowest_price = (
    SELECT MIN(price) FROM price_history ph WHERE ph.product_id = products.product_id
);
