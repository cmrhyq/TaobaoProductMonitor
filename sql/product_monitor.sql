/*
 Navicat Premium Data Transfer

 Source Server         : MySQL_Local_3306
 Source Server Type    : MySQL
 Source Server Version : 80021
 Source Host           : localhost:3306
 Source Schema         : product_monitor

 Target Server Type    : MySQL
 Target Server Version : 80021
 File Encoding         : 65001

 Date: 18/04/2024 11:06:50
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE database if NOT EXISTS `product_monitor` default character set utf8mb4 collate utf8mb4_unicode_ci;
use `product_monitor`;

-- ----------------------------
-- Table structure for price_change
-- ----------------------------
DROP TABLE IF EXISTS `price_change`;
CREATE TABLE `price_change`  (
  `price_id` int NOT NULL AUTO_INCREMENT COMMENT '价格id',
  `product_id` int NULL DEFAULT NULL COMMENT '产品表id',
  `price` decimal(10, 2) NULL DEFAULT NULL COMMENT '第一次的价格',
  `gmt_create` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_modified` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`price_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for products
-- ----------------------------
DROP TABLE IF EXISTS `products`;
CREATE TABLE `products`  (
  `product_id` int NOT NULL AUTO_INCREMENT COMMENT '商品id',
  `user_id` int NULL DEFAULT NULL COMMENT '用户id',
  `platform` varchar(20) CHARACTER SET utf8 COLLATE utf8_general_ci NULL DEFAULT NULL COMMENT '平台',
  `product_url` text CHARACTER SET utf8 COLLATE utf8_general_ci NULL COMMENT '商品链接',
  `product_name` text CHARACTER SET utf8 COLLATE utf8_general_ci NULL COMMENT '商品名称',
  `product_tk` varchar(30) CHARACTER SET utf8 COLLATE utf8_general_ci NULL DEFAULT NULL COMMENT '商品url中的tk',
  `monitor_status` int NULL DEFAULT 10 COMMENT '10=未开始, 11=监控中, 12=已结束',
  `notify_email` varchar(50) CHARACTER SET utf8 COLLATE utf8_general_ci NULL DEFAULT NULL COMMENT '接收通知的邮件地址',
  `gmt_create` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `gmt_modified` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`product_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 18 CHARACTER SET = utf8 COLLATE = utf8_general_ci ROW_FORMAT = Dynamic;

insert into store.products (product_id, user_id, platform, product_url, product_name, product_tk, monitor_status, notify_email, gmt_create, gmt_modified)
values  (19, 1, '淘宝', 'https://m.tb.cn/h.5zxyK10h65Gy9AU?tk=X2X2WKIqj7', '优衣库女装麻混纺吊带连衣裙(打褶高腰时尚法式轻盈新款)466540', 'X2X2WKIqj7o ', 11, 'cmrhyq@163.com', '2024-04-18 00:43:20', '2024-04-25 21:18:06'),
        (20, 1, '淘宝', 'https://m.tb.cn/h.5zxz3j69cN5go4k?tk=XUymWKIqxIz', '优衣库女装网眼V领短针织开衫长袖薄外套空调衫2024新款468541', 'XUymWKIqxIz', 11, 'cmrhyq@163.com', '2024-04-18 00:43:20', '2024-04-25 21:18:06');

commit;
