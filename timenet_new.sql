-- ============================================================
--  TimeNet Cafe — Customer Kiosk Database
--  Compatible with: XAMPP / MariaDB / MySQL 5.7+
--  Database: timenet
-- ============================================================

CREATE DATABASE IF NOT EXISTS `timenet`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `timenet`;

-- ------------------------------------------------------------
--  TABLE: computers
--  Tracks every physical PC in the café.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `computers` (
  `id`                 VARCHAR(64)   NOT NULL,        -- e.g. "pc-01"
  `name`               VARCHAR(128)  NOT NULL,        -- display name, e.g. "PC 01"
  `status`             ENUM(
                         'available',
                         'occupied',
                         'maintenance'
                       ) NOT NULL DEFAULT 'available',
  `current_session_id` VARCHAR(128)  DEFAULT NULL,    -- FK → sessions.id (nullable)
  `created_at`         BIGINT        NOT NULL
                         DEFAULT (UNIX_TIMESTAMP(NOW(3)) * 1000),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ------------------------------------------------------------
--  TABLE: users
--  id = username (natural key, as used in the application).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id`                 VARCHAR(64)   NOT NULL,        -- same as username
  `username`           VARCHAR(64)   NOT NULL,
  `password`           VARCHAR(255)  NOT NULL,        -- plain-text in app; hash recommended
  `role`               ENUM('customer','admin')
                         NOT NULL DEFAULT 'customer',
  `registered_on_pc`   VARCHAR(64)   DEFAULT NULL,    -- FK → computers.id
  `created_at`         BIGINT        NOT NULL,        -- epoch-ms
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_username` (`username`),
  KEY `idx_users_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ------------------------------------------------------------
--  TABLE: sessions
--  id = ses-<username>-<epoch_ms>
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sessions` (
  `id`            VARCHAR(128)  NOT NULL,
  `username`      VARCHAR(64)   NOT NULL,             -- FK → users.username
  `computer_id`   VARCHAR(64)   DEFAULT NULL,         -- FK → computers.id
  `duration`      INT           NOT NULL DEFAULT 0,   -- purchased minutes
  `cost`          DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `status`        ENUM(
                    'pending_voucher',    -- cash: waiting for cashier
                    'pending_add_time',   -- add-time cash voucher
                    'active',            -- session running
                    'paused',            -- user paused
                    'completed',         -- ended normally
                    'cancelled'          -- user or system cancelled
                  ) NOT NULL DEFAULT 'pending_voucher',
  `start_time`    BIGINT        DEFAULT NULL,          -- epoch-ms, set when activated
  `end_time`      BIGINT        DEFAULT NULL,          -- epoch-ms, set when completed
  `paused_at`     BIGINT        DEFAULT NULL,          -- epoch-ms, set when paused
  `paused_remain` BIGINT        DEFAULT NULL,          -- ms remaining at pause
  `voucher_code`  VARCHAR(32)   DEFAULT NULL,          -- e.g. TNV-XXXXXXXX
  PRIMARY KEY (`id`),
  KEY `idx_sessions_username`   (`username`),
  KEY `idx_sessions_computer`   (`computer_id`),
  KEY `idx_sessions_status`     (`status`),
  KEY `idx_sessions_user_status`(`username`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ------------------------------------------------------------
--  TABLE: payments
--  id = pay-<username>-<epoch_ms>
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `payments` (
  `id`         VARCHAR(128)  NOT NULL,
  `session_id` VARCHAR(128)  NOT NULL,               -- FK → sessions.id
  `username`   VARCHAR(64)   NOT NULL,               -- FK → users.username
  `amount`     DECIMAL(10,2) NOT NULL,
  `method`     ENUM('cash','gcash','maya','online')
                 NOT NULL DEFAULT 'cash',
  `timestamp`  BIGINT        NOT NULL,               -- epoch-ms
  `receipt_no` VARCHAR(32)   NOT NULL,               -- RN-DD-MM-YYYY-XXX
  `status`     ENUM('pending','completed','failed','refunded')
                 NOT NULL DEFAULT 'pending',
  PRIMARY KEY (`id`),
  KEY `idx_payments_session`  (`session_id`),
  KEY `idx_payments_username` (`username`),
  KEY `idx_payments_status`   (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  SEED DATA
-- ============================================================

-- ── Computers (add / rename to match your café layout) ──────
INSERT IGNORE INTO `computers` (`id`, `name`, `status`, `created_at`) VALUES
  ('pc-01', 'PC 01', 'available', UNIX_TIMESTAMP(NOW(3)) * 1000),
  ('pc-02', 'PC 02', 'available', UNIX_TIMESTAMP(NOW(3)) * 1000),
  ('pc-03', 'PC 03', 'available', UNIX_TIMESTAMP(NOW(3)) * 1000),
  ('pc-04', 'PC 04', 'available', UNIX_TIMESTAMP(NOW(3)) * 1000),
  ('pc-05', 'PC 05', 'available', UNIX_TIMESTAMP(NOW(3)) * 1000);

-- ── Admin user (change password before going live!) ─────────
INSERT IGNORE INTO `users`
  (`id`, `username`, `password`, `role`, `registered_on_pc`, `created_at`)
VALUES
  ('admin', 'admin', 'admin1234', 'admin', 'pc-01',
   UNIX_TIMESTAMP(NOW(3)) * 1000);

-- ── Sample customer (for testing) ───────────────────────────
INSERT IGNORE INTO `users`
  (`id`, `username`, `password`, `role`, `registered_on_pc`, `created_at`)
VALUES
  ('testuser', 'testuser', 'testpass', 'customer', 'pc-01',
   UNIX_TIMESTAMP(NOW(3)) * 1000);


-- ============================================================
--  HELPFUL VIEWS  (optional — aids admin portal / reporting)
-- ============================================================

-- Active sessions with computer name
CREATE OR REPLACE VIEW `v_active_sessions` AS
SELECT
  s.id            AS session_id,
  s.username,
  c.name          AS computer_name,
  s.duration,
  s.cost,
  s.start_time,
  s.voucher_code,
  FROM_UNIXTIME(s.start_time / 1000)
    + INTERVAL s.duration MINUTE AS end_datetime
FROM `sessions` s
LEFT JOIN `computers` c ON c.id = s.computer_id
WHERE s.status = 'active';

-- Paused sessions summary
CREATE OR REPLACE VIEW `v_paused_sessions` AS
SELECT
  s.id              AS session_id,
  s.username,
  c.name            AS computer_name,
  s.duration,
  s.cost,
  s.paused_at,
  ROUND(s.paused_remain / 60000, 2) AS remaining_minutes
FROM `sessions` s
LEFT JOIN `computers` c ON c.id = s.computer_id
WHERE s.status = 'paused';

-- Payment history
CREATE OR REPLACE VIEW `v_payment_history` AS
SELECT
  p.id          AS payment_id,
  p.receipt_no,
  p.username,
  p.amount,
  p.method,
  p.status      AS payment_status,
  FROM_UNIXTIME(p.timestamp / 1000) AS paid_at,
  s.duration,
  c.name        AS computer_name
FROM `payments` p
LEFT JOIN `sessions`  s ON s.id = p.session_id
LEFT JOIN `computers` c ON c.id = s.computer_id
ORDER BY p.timestamp DESC;
