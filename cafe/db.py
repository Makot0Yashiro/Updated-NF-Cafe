"""Connects the website to MySQL with the official MySQL Connector/Python package.
On start-up the database sets itself up: every table in database/nf_cafe.sql (the one source of truth for the table definitions),
newer columns for older databases, the starter menu (once) and the first admin account."""
import os, re
import mysql.connector
from flask import g
from werkzeug.security import generate_password_hash
from .config import MYSQL, PRODUCTION

IntegrityError = mysql.connector.errors.IntegrityError
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "nf_cafe.sql")


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


def _connect(**override):
    return mysql.connector.connect(**{**MYSQL, **override}, charset="utf8mb4")


def get_db():
    if "db" not in g:
        g.db = DB(_connect())
    return g.db


def close_db(e=None):
    d = g.pop("db", None)
    if d:
        d.close()


# Columns added after the first release, for databases created from an older nf_cafe.sql (CREATE TABLE IF NOT EXISTS skips those).
UPGRADES = [("orders", "pay_status", "VARCHAR(20) DEFAULT 'unpaid'"), ("orders", "pay_ref", "VARCHAR(60)"),
            ("orders", "pay_at", "VARCHAR(40)"), ("orders", "dest_address", "VARCHAR(255)"),
            ("orders", "stock_json", "TEXT"), ("orders", "stock_returned", "TINYINT DEFAULT 0")]


def schema_statements():
    """The CREATE TABLE statements from database/nf_cafe.sql, in file order."""
    with open(SCHEMA_FILE, encoding="utf-8") as f:
        sql = re.sub(r"--[^\n]*", "", f.read())             # drop comments (none of the table definitions contain "--")
    return [s.strip() for s in sql.split(";") if s.strip().upper().startswith("CREATE TABLE")]


def _ensure_admin(cur):
    cur.execute("SELECT 1 FROM users WHERE is_admin=1 LIMIT 1")
    if cur.fetchone():
        return
    email = os.environ.get("ADMIN_EMAIL", "admin@newfoundcafe.com").strip().lower()
    pw = os.environ.get("ADMIN_PASSWORD", "")
    if not pw:
        if PRODUCTION:
            raise SystemExit("\nThere is no admin account yet. Set ADMIN_EMAIL and ADMIN_PASSWORD, then start the app again.\n")
        pw = "admin123"
    cur.execute("SELECT 1 FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        cur.execute("UPDATE users SET is_admin=1 WHERE email=%s", (email,))
    else:
        cur.execute("INSERT INTO users(name,email,password_hash,is_admin) VALUES('Admin',%s,%s,1)", (email, generate_password_hash(pw)))
    print(f"\n  Admin account ready: {email}" + ("" if PRODUCTION or os.environ.get("ADMIN_PASSWORD") else " / admin123  (set ADMIN_EMAIL / ADMIN_PASSWORD to change)") + "\n")


def setup(conn):
    """Create / upgrade / seed. Safe to repeat; the caller holds the setup lock."""
    cur = conn.cursor()
    for ddl in schema_statements():
        cur.execute(ddl)
    for table, col, ddl in UPGRADES:
        cur.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (col,))
        if not cur.fetchall():
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    cur.execute("SELECT COUNT(*) FROM categories")
    if not cur.fetchone()[0]:                      # first run with inventory: load the starter menu once
        from .inventory_seed import seed
        seed(cur)
        print("\n  Starter menu and inventory added (manage them in Admin > Inventory / Menu items).\n")
    cur.execute("UPDATE orders SET order_type='pickup' WHERE order_type='takeaway'")
    cur.execute("UPDATE orders SET payment='online' WHERE payment IN ('gcash','maya','card')")
    cur.execute("UPDATE orders SET pay_status='pending' WHERE payment='online' AND pay_status='unpaid'")
    cur.execute("UPDATE users SET pay_method='online' WHERE pay_method IN ('gcash','maya','card')")
    _ensure_admin(cur)
    conn.commit()


def _open_for_setup():
    try:
        return _connect()
    except mysql.connector.Error as e:
        if e.errno == 1049 and not PRODUCTION:    # unknown database (local): create it
            c = _connect(database=None)
            c.cursor().execute(f"CREATE DATABASE `{MYSQL['database']}` DEFAULT CHARACTER SET utf8mb4")
            c.close()
            return _connect()
        raise SystemExit(f"\nCould not connect to MySQL: {e}\n"
                         "1) Make sure the MySQL server is running / reachable.\n"
                         "2) Check DATABASE_URL, or MYSQL_HOST / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE (see .env.example).\n"
                         "3) Hosted MySQL usually needs SSL: set MYSQL_SSL_CA (or MYSQL_SSL=required).\n")


def init_app(app):
    app.teardown_appcontext(close_db)
    conn = _open_for_setup()
    cur = conn.cursor()
    try:
        cur.execute("SELECT GET_LOCK('nf_cafe_setup', 30)")   # several workers start at once: only one sets up at a time
        if cur.fetchone()[0] != 1:
            raise SystemExit("\nTimed out waiting for another copy of the app to finish setting up the database.\n")
        setup(conn)
    finally:
        try:
            cur.execute("SELECT RELEASE_LOCK('nf_cafe_setup')"); cur.fetchall()
        finally:
            conn.close()
