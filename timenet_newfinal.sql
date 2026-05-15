-- ============================================================
--  TimeNet Cafe — Customer Kiosk Database
--  Compatible with: XAMPP / MariaDB / MySQL 5.7+
--  Database: timenet
-- ============================================================
--
--  TIMESTAMP FORMAT (human-readable, no epoch-ms anywhere):
--    created_at    → DATETIME  displayed as  May 14, 2026 09:30:00 AM
--    start_time    → DATETIME  displayed as  May 14, 2026 09:30:00 AM
--    end_time      → DATETIME  displayed as  May 14, 2026 11:30:00 AM
--    paused_at     → DATETIME  displayed as  May 14, 2026 10:15:00 AM
--    timestamp     → DATETIME  (payments)    displayed as  May 14, 2026 10:15:00 AM
--    paused_remain → TIME      HH:MM:SS  e.g.  01:23:45
--
--  ID FORMAT (no random numbers, no epoch-ms):
--    sessions  → ses-<username>-MM-DD-YYYY-HH-MM-SS
--    payments  → pay-<username>-MM-DD-YYYY-HH-MM-SS
--    receipt   → RN-MM-DD-YYYY-HH-MM-SS
-- ============================================================

CREATE DATABASE IF NOT EXISTS `timenet`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `timenet`;

-- ------------------------------------------------------------
--  TABLE: computers
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `computers` (
  `id`                 VARCHAR(64)   NOT NULL,
  `name`               VARCHAR(128)  NOT NULL,
  `status`             ENUM('available','occupied','maintenance')
                         NOT NULL DEFAULT 'available',
  `current_session_id` VARCHAR(128)  DEFAULT NULL,
  `created_at`         DATETIME      NOT NULL DEFAULT NOW(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ------------------------------------------------------------
--  TABLE: users
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id`               VARCHAR(64)  NOT NULL,
  `username`         VARCHAR(64)  NOT NULL,
  `password`         VARCHAR(255) NOT NULL,
  `role`             ENUM('customer','admin') NOT NULL DEFAULT 'customer',
  `registered_on_pc` VARCHAR(64)  DEFAULT NULL,
  `created_at`       DATETIME     NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_username` (`username`),
  KEY `idx_users_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ------------------------------------------------------------
--  TABLE: sessions
--  id            = ses-<username>-MM-DD-YYYY-HH-MM-SS
--  paused_remain = TIME column  e.g.  '01:23:45'
--                  Stores the exact remaining HH:MM:SS when paused.
--                  Python writes it as  '%H:%M:%S'  string.
--                  MySQL/MariaDB TIME range: -838:59:59 .. 838:59:59
--                  so even an 8-hour session fits comfortably.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sessions` (
  `id`            VARCHAR(128)  NOT NULL,
  `username`      VARCHAR(64)   NOT NULL,
  `computer_id`   VARCHAR(64)   DEFAULT NULL,
  `duration`      INT           NOT NULL DEFAULT 0,
  `cost`          DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `status`        ENUM(
                    'pending_voucher',
                    'pending_add_time',
                    'active',
                    'paused',
                    'completed',
                    'cancelled'
                  ) NOT NULL DEFAULT 'pending_voucher',
  `start_time`    DATETIME      DEFAULT NULL,
  `end_time`      DATETIME      DEFAULT NULL,
  `paused_at`     DATETIME      DEFAULT NULL,
  `paused_remain` TIME          DEFAULT NULL,   -- HH:MM:SS remaining (e.g. '01:23:45')
  `voucher_code`  VARCHAR(32)   DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_sessions_username`    (`username`),
  KEY `idx_sessions_computer`    (`computer_id`),
  KEY `idx_sessions_status`      (`status`),
  KEY `idx_sessions_user_status` (`username`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ------------------------------------------------------------
--  TABLE: payments
--  id         = pay-<username>-MM-DD-YYYY-HH-MM-SS
--  receipt_no = RN-MM-DD-YYYY-HH-MM-SS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `payments` (
  `id`         VARCHAR(128)  NOT NULL,
  `session_id` VARCHAR(128)  NOT NULL,
  `username`   VARCHAR(64)   NOT NULL,
  `amount`     DECIMAL(10,2) NOT NULL,
  `method`     ENUM('cash','gcash','maya','online') NOT NULL DEFAULT 'cash',
  `timestamp`  DATETIME      NOT NULL,
  `receipt_no` VARCHAR(48)   NOT NULL,
  `status`     ENUM('pending','completed','failed','refunded') NOT NULL DEFAULT 'pending',
  PRIMARY KEY (`id`),
  KEY `idx_payments_session`  (`session_id`),
  KEY `idx_payments_username` (`username`),
  KEY `idx_payments_status`   (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  SEED DATA
-- ============================================================

INSERT IGNORE INTO `computers` (`id`, `name`, `status`, `created_at`) VALUES
  ('pc-01', 'PC 01', 'available', NOW()),
  ('pc-02', 'PC 02', 'available', NOW()),
  ('pc-03', 'PC 03', 'available', NOW()),
  ('pc-04', 'PC 04', 'available', NOW()),
  ('pc-05', 'PC 05', 'available', NOW());

INSERT IGNORE INTO `users`
  (`id`, `username`, `password`, `role`, `registered_on_pc`, `created_at`)
VALUES
  ('admin', 'admin', 'admin1234', 'admin', 'pc-01', NOW());

INSERT IGNORE INTO `users`
  (`id`, `username`, `password`, `role`, `registered_on_pc`, `created_at`)
VALUES
  ('testuser', 'testuser', 'testpass', 'customer', 'pc-01', NOW());


-- ============================================================
--  VIEWS
--  All human-readable formats:
--    Dates      → %M %d, %Y          e.g.  May 14, 2026
--    Times      → %h:%i:%s %p        e.g.  09:30:00 AM
--    Date+Time  → %M %d, %Y %h:%i:%s %p   e.g.  May 14, 2026 09:30:00 AM
-- ============================================================

-- ------------------------------------------------------------
--  VIEW: v_active_sessions
--  Shows: session info, start_time, computed end_time (both as
--         full Month DD, YYYY HH:MM:SS AM/PM strings)
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW `v_active_sessions` AS
SELECT
  s.id                                                            AS session_id,
  s.username,
  c.name                                                          AS computer_name,
  s.duration,
  s.cost,
  DATE_FORMAT(s.start_time, '%M %d, %Y %h:%i:%s %p')             AS start_time,
  DATE_FORMAT(
    DATE_ADD(s.start_time, INTERVAL s.duration MINUTE),
    '%M %d, %Y %h:%i:%s %p'
  )                                                               AS end_time,
  s.voucher_code
FROM `sessions` s
LEFT JOIN `computers` c ON c.id = s.computer_id
WHERE s.status = 'active';


-- ------------------------------------------------------------
--  VIEW: v_paused_sessions
--
--  FIX: remaining_minutes was incorrectly returning a decimal like
--       83.75 which looks like "83 minutes 75 seconds" but is actually
--       "83.75 minutes" (i.e. 83 minutes and 45 seconds).
--
--  FIXED columns:
--    remaining_time    → raw TIME value  'HH:MM:SS'   (unchanged)
--    remaining_h       → whole hours remaining         (e.g. 1)
--    remaining_m       → whole minutes within the hour (e.g. 23)
--    remaining_s       → whole seconds within the minute (e.g. 45)
--    remaining_total_minutes → whole minutes only (FLOOR), no decimals
--                              e.g. 83  (not 83.75)
--    remaining_display → human-friendly string  e.g. '1h 23m 45s'
--
--  The old `remaining_minutes` decimal column is REMOVED to prevent
--  misuse.  Use remaining_total_minutes (whole) or remaining_time
--  (HH:MM:SS) instead.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW `v_paused_sessions` AS
SELECT
  s.id                                                            AS session_id,
  s.username,
  c.name                                                          AS computer_name,
  s.duration,
  s.cost,
  DATE_FORMAT(s.paused_at, '%M %d, %Y %h:%i:%s %p')              AS paused_at,

  -- Raw TIME value exactly as stored: 'HH:MM:SS'
  s.paused_remain                                                 AS remaining_time,

  -- Broken-out components (all whole integers, no decimals)
  FLOOR( TIME_TO_SEC(s.paused_remain) / 3600 )                   AS remaining_h,
  FLOOR( (TIME_TO_SEC(s.paused_remain) % 3600) / 60 )            AS remaining_m,
  TIME_TO_SEC(s.paused_remain) % 60                               AS remaining_s,

  -- Total whole minutes remaining (FLOOR — no decimal confusion)
  -- e.g. 1h 23m 45s  →  83   (not 83.75)
  FLOOR( TIME_TO_SEC(s.paused_remain) / 60 )                     AS remaining_total_minutes,

  -- Human-friendly display string  e.g. '1h 23m 45s'
  CONCAT(
    FLOOR( TIME_TO_SEC(s.paused_remain) / 3600 ),        'h ',
    FLOOR( (TIME_TO_SEC(s.paused_remain) % 3600) / 60 ), 'm ',
    TIME_TO_SEC(s.paused_remain) % 60,                   's'
  )                                                               AS remaining_display

FROM `sessions` s
LEFT JOIN `computers` c ON c.id = s.computer_id
WHERE s.status = 'paused';


-- ------------------------------------------------------------
--  VIEW: v_payment_history
--  Shows: paid_at as Month DD, YYYY HH:MM:SS AM/PM
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW `v_payment_history` AS
SELECT
  p.id                                                            AS payment_id,
  p.receipt_no,
  p.username,
  p.amount,
  p.method,
  p.status                                                        AS payment_status,
  DATE_FORMAT(p.timestamp, '%M %d, %Y %h:%i:%s %p')              AS paid_at,
  s.duration,
  c.name                                                          AS computer_name,
  DATE_FORMAT(s.start_time, '%M %d, %Y %h:%i:%s %p')             AS session_start,
  DATE_FORMAT(s.end_time,   '%M %d, %Y %h:%i:%s %p')             AS session_end
FROM `payments` p
LEFT JOIN `sessions`  s ON s.id  = p.session_id
LEFT JOIN `computers` c ON c.id  = s.computer_id
ORDER BY p.timestamp DESC;


-- ------------------------------------------------------------
--  VIEW: v_completed_sessions
--  Shows all finished sessions with full date+time strings
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW `v_completed_sessions` AS
SELECT
  s.id                                                            AS session_id,
  s.username,
  c.name                                                          AS computer_name,
  s.duration,
  s.cost,
  DATE_FORMAT(s.start_time, '%M %d, %Y %h:%i:%s %p')             AS start_time,
  DATE_FORMAT(s.end_time,   '%M %d, %Y %h:%i:%s %p')             AS end_time,
  s.status
FROM `sessions` s
LEFT JOIN `computers` c ON c.id = s.computer_id
WHERE s.status IN ('completed', 'cancelled')
ORDER BY s.end_time DESC;