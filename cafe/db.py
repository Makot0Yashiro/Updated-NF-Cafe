"""Connects the website to the MySQL database defined in database/nf_cafe.sql
(run that file once in MySQL Workbench). Uses the official MySQL Connector/Python package."""
import mysql.connector
from flask import g
from .config import MYSQL

IntegrityError = mysql.connector.errors.IntegrityError


class DB:
    """Thin wrapper so the rest of the app can call db.execute(sql, params) with ? placeholders."""
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        cur = self.conn.cursor(dictionary=True, buffered=True)
        cur.execute(sql.replace("?", "%s"), params)
        return cur

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def _connect():
    return mysql.connector.connect(**MYSQL, charset="utf8mb4")


def get_db():
    if "db" not in g:
        g.db = DB(_connect())
    return g.db


def close_db(e=None):
    d = g.pop("db", None)
    if d:
        d.close()


UPGRADES = [("orders", "pay_status", "VARCHAR(20) DEFAULT 'unpaid'"), ("orders", "pay_ref", "VARCHAR(60)"),
            ("orders", "pay_at", "VARCHAR(40)"), ("orders", "dest_address", "VARCHAR(255)"),
            ("orders", "stock_json", "TEXT"), ("orders", "stock_returned", "TINYINT DEFAULT 0")]
OTP_TABLE = """CREATE TABLE IF NOT EXISTS email_otps(
  id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(190) NOT NULL, purpose VARCHAR(10) NOT NULL, code_hash VARCHAR(64) NOT NULL,
  payload TEXT, attempts INT DEFAULT 0, expires_at VARCHAR(40) NOT NULL, created_at VARCHAR(40) NOT NULL, INDEX(email)) DEFAULT CHARSET=utf8mb4"""
# Menu + inventory (same definitions as database/nf_cafe.sql)
INVENTORY_TABLES = [
    """CREATE TABLE IF NOT EXISTS categories(
  id VARCHAR(40) PRIMARY KEY, name VARCHAR(60) NOT NULL UNIQUE, group_name VARCHAR(60) NOT NULL,
  color VARCHAR(7) NOT NULL DEFAULT '#8a5a33', emoji VARCHAR(16) NOT NULL, sort INT NOT NULL DEFAULT 0) DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS ingredients(
  id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(80) NOT NULL UNIQUE, unit VARCHAR(4) NOT NULL,
  stock DECIMAL(12,3) NOT NULL DEFAULT 0, low_at DECIMAL(12,3) NOT NULL DEFAULT 0) DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS menu_items(
  id VARCHAR(40) PRIMARY KEY, name VARCHAR(80) NOT NULL UNIQUE, cat_id VARCHAR(40) NOT NULL, price DECIMAL(10,2) NOT NULL,
  img VARCHAR(300), active TINYINT NOT NULL DEFAULT 1, sort INT NOT NULL DEFAULT 0,
  FOREIGN KEY (cat_id) REFERENCES categories(id)) DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS menu_item_ingredients(
  item_id VARCHAR(40) NOT NULL, ingredient_id INT NOT NULL, qty DECIMAL(12,3) NOT NULL, PRIMARY KEY (item_id, ingredient_id),
  FOREIGN KEY (item_id) REFERENCES menu_items(id) ON DELETE CASCADE,
  FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT) DEFAULT CHARSET=utf8mb4""",
]


def _upgrade(conn):
    """Adds anything newer than the .sql file you ran (safe to repeat)."""
    cur = conn.cursor()
    for table, col, ddl in UPGRADES:
        cur.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (col,))
        if not cur.fetchall():
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    cur.execute(OTP_TABLE)
    for ddl in INVENTORY_TABLES:
        cur.execute(ddl)
    cur.execute("SELECT COUNT(*) FROM categories")
    if not cur.fetchone()[0]:                      # first run with inventory: load the starter menu once
        from .inventory_seed import seed
        seed(cur)
        print("\n  Starter menu and inventory added (manage them in Admin > Inventory / Menu items).\n")
    cur.execute("UPDATE orders SET order_type='pickup' WHERE order_type='takeaway'")
    cur.execute("UPDATE orders SET payment='online' WHERE payment IN ('gcash','maya','card')")
    cur.execute("UPDATE orders SET pay_status='pending' WHERE payment='online' AND pay_status='unpaid'")
    cur.execute("UPDATE users SET pay_method='online' WHERE pay_method IN ('gcash','maya','card')")
    conn.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SHOW TABLES LIKE 'orders'")
        ready = cur.fetchone()
        conn.close()
    except mysql.connector.Error as e:
        raise SystemExit(f"\nCould not connect to MySQL: {e}\n"
                         "1) Make sure MySQL Server is running.\n"
                         "2) Check the user / password in cafe/config.py (same as your MySQL Workbench connection).\n"
                         "3) Run database/nf_cafe.sql in MySQL Workbench to create the database.\n")
    if not ready:
        raise SystemExit("\nThe tables don't exist yet. Open database/nf_cafe.sql in MySQL Workbench and run it first.\n")
    conn = _connect()
    _upgrade(conn)
    conn.close()
