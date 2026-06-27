-- =============================================================
-- scdb_mysql_speed 测试环境初始化脚本
-- 目标服务器: 10.10.10.150
-- 使用方法: mysql -h 10.10.10.150 -u root -p < create_test_db.sql
-- =============================================================

-- 1. 创建测试数据库
CREATE DATABASE IF NOT EXISTS `test_5001`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

-- 2. 创建测试用户并授权
CREATE USER IF NOT EXISTS 'test5001'@'%' IDENTIFIED BY 'Love2026';
GRANT ALL PRIVILEGES ON `test_5001`.* TO 'test5001'@'%';
FLUSH PRIVILEGES;

-- 3. 创建测试表
USE `test_5001`;

CREATE TABLE IF NOT EXISTS `t_test5001` (
    `id`   INT          NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(255) NOT NULL DEFAULT '',
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
