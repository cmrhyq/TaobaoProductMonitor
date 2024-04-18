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

commit;
