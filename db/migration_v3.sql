-- Migration from v2 to v3
-- Adds the original_price column to price_history for subsidized/promo price tracking.
-- Note: for SQLite the migration runs automatically in init_db(); this script is
-- the reference for MySQL users.

ALTER TABLE price_history ADD COLUMN original_price DECIMAL(10, 2) NULL COMMENT '优惠前挂牌价，检测到补贴/促销价时记录';
