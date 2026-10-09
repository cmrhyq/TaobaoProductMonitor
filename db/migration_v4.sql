-- Migration from v3 to v4
-- Adds product_snapshot: the full product detail captured by each fetch
-- (title / skus / attributes / shop / images), while price_history stays a
-- narrow time series.
--
-- 价格语义：price_current = 实付价（优惠后），price_original = 优惠前价。
--
-- 说明：SQLite 由 init_db() 里的 Base.metadata.create_all() 自动建表，
-- 无需手工执行；本脚本是 MySQL 用户的参考。
--
-- ⚠️ 已有的 db/ProductMonitor.db 只需要跑这一个脚本（或用 create_all）。
-- 绝对不要对存量库执行 db/init_sqlite.sql —— 它含示例数据 INSERT，会污染真实数据。

CREATE TABLE IF NOT EXISTS product_snapshot (
    snapshot_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '快照ID',
    product_id INT NOT NULL COMMENT '关联 products.product_id',
    item_id VARCHAR(100) NULL COMMENT '淘宝商品ID',
    title VARCHAR(500) NULL COMMENT '抓取时的商品标题',
    subtitle TEXT NULL COMMENT '副标题',
    price_current DECIMAL(10, 2) NULL COMMENT '实付价（优惠后）',
    price_original DECIMAL(10, 2) NULL COMMENT '优惠前价',
    price_low DECIMAL(10, 2) NULL COMMENT 'SKU 区间最低价',
    price_high DECIMAL(10, 2) NULL COMMENT 'SKU 区间最高价',
    price_text VARCHAR(200) NULL COMMENT '价格原文，便于核对语义',
    promotions_json LONGTEXT NULL COMMENT '促销信息 JSON',
    stock_total INT NULL COMMENT '总库存',
    sold_text VARCHAR(100) NULL COMMENT '销量文案',
    skus_json LONGTEXT NULL COMMENT 'SKU 明细 JSON',
    attributes_json LONGTEXT NULL COMMENT '商品参数 JSON',
    images_json LONGTEXT NULL COMMENT '主图 JSON',
    shop_json LONGTEXT NULL COMMENT '店铺信息 JSON',
    shop_name VARCHAR(200) NULL COMMENT '店铺名（便利列）',
    source VARCHAR(50) NULL COMMENT '数据来源，如 ssr-pc / dom-pc',
    fetched_at DATETIME NULL COMMENT '抓取时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product_snapshot_product_id (product_id),
    INDEX idx_product_snapshot_fetched_at (fetched_at),
    INDEX idx_product_snapshot_item_id (item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品抓取快照表';
