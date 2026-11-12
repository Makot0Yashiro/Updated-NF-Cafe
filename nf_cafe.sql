-- =====================================================================
--  New Found Cafe - database
--  Open this file in MySQL Workbench (File > Open SQL Script...), then press
--  the lightning-bolt button (Execute) to create the database and tables.
--  Safe to run more than once: existing data is kept.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS nf_cafe DEFAULT CHARACTER SET utf8mb4;
USE nf_cafe;

-- Customer and admin accounts (is_admin = 1 -> staff, signs in at /admin-login)
CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(100) NOT NULL,          -- username shown on the site
  email         VARCHAR(190) NOT NULL UNIQUE,
  phone         VARCHAR(30),                    -- contact number
  password_hash VARCHAR(255) NOT NULL,          -- hashed by the app, never plain text
  address       VARCHAR(255),                   -- saved delivery address
  addr_lat      DOUBLE,                         -- saved delivery pin
  addr_lng      DOUBLE,
  pay_method    VARCHAR(20) DEFAULT 'cash',     -- cash / gcash / maya / card
  pay_account   VARCHAR(30),                    -- e-wallet number (no card details)
  is_admin      TINYINT DEFAULT 0,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) DEFAULT CHARSET=utf8mb4;

-- Every order placed on the website
CREATE TABLE IF NOT EXISTS orders (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  customer_name VARCHAR(100),
  order_type    VARCHAR(20),                    -- dine-in / takeaway / delivery
  table_no      VARCHAR(10),
  payment       VARCHAR(20),
  note          VARCHAR(255),
  items_json    TEXT,                           -- ordered items as JSON
  subtotal      DOUBLE,
  coupon        VARCHAR(30),
  discount      DOUBLE,
  total         DOUBLE,
  status        VARCHAR(30) DEFAULT 'Received', -- Received, Preparing, Ready, Out for delivery, Delivered, Completed, Cancelled
  status_at     VARCHAR(40),                    -- when the status last changed (UTC)
  dest_lat      DOUBLE,                         -- delivery destination
  dest_lng      DOUBLE,
  cur_lat       DOUBLE,                         -- current location shown on the tracking map
  cur_lng       DOUBLE,
  pay_status    VARCHAR(20) DEFAULT 'unpaid',   -- unpaid (cash) / pending (QR, waiting for admin) / paid / rejected
  pay_ref       VARCHAR(60),                    -- reference number the customer typed after paying by QR
  pay_at        VARCHAR(40),                    -- when the admin confirmed / rejected the payment
  dest_address  VARCHAR(255),                   -- delivery address typed at checkout
  created_at    VARCHAR(40) NOT NULL,           -- when the order was placed (UTC)
  INDEX (user_id),
  INDEX (status),
  FOREIGN KEY (user_id) REFERENCES users(id)
) DEFAULT CHARSET=utf8mb4;

-- One-time email codes (OTP) for sign-up / login
CREATE TABLE IF NOT EXISTS email_otps (
  id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(190) NOT NULL, purpose VARCHAR(10) NOT NULL, code_hash VARCHAR(64) NOT NULL,
  payload TEXT, attempts INT DEFAULT 0, expires_at VARCHAR(40) NOT NULL, created_at VARCHAR(40) NOT NULL, INDEX (email)
) DEFAULT CHARSET=utf8mb4;

-- Starter admin account:  admin@newfoundcafe.com  /  admin123   (change the password after first login!)
INSERT INTO users (name, email, password_hash, is_admin)
VALUES ('Admin', 'admin@newfoundcafe.com', 'scrypt:32768:8:1$oxeIAqPemGViYc1f$ba1c3d67f766df703252ffa77587c63c3d08496f067515f5f362ea9c4ea55473fffcb39e8c425100fa635eff7f9669238adef6df45743e53cd47381e76bb715c', 1)
ON DUPLICATE KEY UPDATE is_admin = 1;

-- ---- Handy queries to try in Workbench ----
-- SELECT * FROM orders ORDER BY id DESC;
-- SELECT status, COUNT(*) AS orders, SUM(total) AS sales FROM orders WHERE status <> 'Cancelled' GROUP BY status;
-- UPDATE orders SET status = 'Preparing' WHERE id = 1;
