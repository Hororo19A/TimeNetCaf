-- ================================================================
--  TimeNet Cafe — MySQL Schema
--  Import this file into phpMyAdmin (XAMPP)
--  Compatible with: customer.py and admin.py
-- ================================================================

-- 1. Create the database
CREATE DATABASE IF NOT EXISTS `timenet`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `timenet`;

-- ================================================================
--  TABLE: users
--  Stores both admin and customer accounts
-- ================================================================
CREATE TABLE IF NOT EXISTS `users` (
  `id`         VARCHAR(64)  NOT NULL,
  `username`   VARCHAR(100) NOT NULL UNIQUE,
  `password`   VARCHAR(255) NOT NULL,
  `role`       ENUM('admin','customer') NOT NULL DEFAULT 'customer',
  `created_at` BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ================================================================
--  TABLE: computers
--  Tracks each PC in the cafe
-- ================================================================
CREATE TABLE IF NOT EXISTS `computers` (
  `id`                  VARCHAR(64)  NOT NULL,
  `name`                VARCHAR(100) NOT NULL,
  `status`              ENUM('available','occupied','maintenance') NOT NULL DEFAULT 'available',
  `current_session_id`  VARCHAR(64)  DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ================================================================
--  TABLE: sessions
--  One row per booking / time session
-- ================================================================
CREATE TABLE IF NOT EXISTS `sessions` (
  `id`           VARCHAR(64)   NOT NULL,
  `user_id`      VARCHAR(64)   NOT NULL DEFAULT '',
  `computer_id`  VARCHAR(64)   NOT NULL DEFAULT '',
  `duration`     INT           NOT NULL DEFAULT 0  COMMENT 'Minutes booked',
  `cost`         DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `status`       ENUM(
                   'pending_voucher',
                   'active',
                   'completed',
                   'cancelled'
                 ) NOT NULL DEFAULT 'pending_voucher',
  `start_time`   BIGINT        DEFAULT NULL COMMENT 'Unix ms when session became active',
  `end_time`     BIGINT        DEFAULT NULL COMMENT 'Unix ms when session completed',
  `cancelled_at` BIGINT        DEFAULT NULL,
  `voucher_code` VARCHAR(32)   DEFAULT NULL COMMENT 'Set for cash payments',
  `created_at`   BIGINT        NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_user_status`     (`user_id`, `status`),
  KEY `idx_computer_status` (`computer_id`, `status`),
  KEY `idx_voucher`         (`voucher_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ================================================================
--  TABLE: payments
--  One row per completed or attempted payment
-- ================================================================
CREATE TABLE IF NOT EXISTS `payments` (
  `id`          VARCHAR(64)   NOT NULL,
  `session_id`  VARCHAR(64)   NOT NULL DEFAULT '',
  `user_id`     VARCHAR(64)   NOT NULL DEFAULT '',
  `amount`      DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `method`      ENUM('cash','gcash','maya','online') NOT NULL DEFAULT 'cash',
  `timestamp`   BIGINT        NOT NULL DEFAULT 0,
  `receipt_no`  VARCHAR(32)   DEFAULT NULL,
  `status`      ENUM('completed','pending','failed') NOT NULL DEFAULT 'pending',
  PRIMARY KEY (`id`),
  KEY `idx_session`   (`session_id`),
  KEY `idx_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ================================================================
--  SEED DATA — default admin account + starter PCs
--  Admin login: username = admin | password = admin123
--  Change the password after first login!
-- ================================================================

INSERT IGNORE INTO `users` (`id`, `username`, `password`, `role`, `created_at`)
VALUES
  ('user-admin-001', 'admin', 'admin123', 'admin', UNIX_TIMESTAMP() * 1000);

INSERT IGNORE INTO `computers` (`id`, `name`, `status`)
VALUES
  ('pc-001', 'PC-01', 'available'),
  ('pc-002', 'PC-02', 'available'),
  ('pc-003', 'PC-03', 'available'),
  ('pc-004', 'PC-04', 'available'),
  ('pc-005', 'PC-05', 'available');


-- ================================================================
--  DONE — import complete
-- ================================================================
