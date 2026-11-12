"""Shared test setup. Every test runs against a throwaway database, nf_cafe_test, created fresh for the run and dropped
afterwards; the real nf_cafe database is never touched. The MySQL password comes from .env (MYSQL_PASSWORD)."""
import os, re, uuid

# Must be set before anything imports cafe.config (it reads the environment once). .env never overrides these.
TEST_DB = "nf_cafe_test"
os.environ.update(MYSQL_DATABASE=TEST_DB, APP_ENV="development", SECRET_KEY="test-secret-key",
                  ADMIN_EMAIL="admin@test.local", ADMIN_PASSWORD="admin-pass-123", MAIL_USERNAME="mailer@test.local")
os.environ.pop("DATABASE_URL", None)

import mysql.connector
import pytest
from flask_mail import email_dispatched
from werkzeug.security import generate_password_hash

import cafe                                      # loads .env (MYSQL_PASSWORD) without overriding the values above
from cafe.config import MYSQL

CSRF = "test-csrf-token"
H = {"X-CSRFToken": CSRF}                        # header for JSON API writes


def connect(database=TEST_DB):
    cfg = {k: v for k, v in MYSQL.items() if k != "database"}
    return mysql.connector.connect(**cfg, database=database, charset="utf8mb4", autocommit=True)


def q(sql, args=()):
    """Run SQL on the test database outside the app (always sees committed data). Returns rows as dicts."""
    c = connect()
    try:
        cur = c.cursor(dictionary=True)
        cur.execute(sql, args)
        return cur.fetchall() if cur.with_rows else []
    finally:
        c.close()


def drop_database(name):
    c = connect(database=None)
    c.cursor().execute(f"DROP DATABASE IF EXISTS `{name}`")
    c.close()


@pytest.fixture(scope="session")
def app():
    try:
        drop_database(TEST_DB)
    except mysql.connector.Error as e:
        pytest.exit(f"Can't reach MySQL ({e}). Copy .env.example to .env and set MYSQL_PASSWORD.", returncode=2)
    application = cafe.create_app()              # creates nf_cafe_test, every table, the starter menu and the admin
    application.config.update(TESTING=True)
    application.extensions["mail"].suppress = True   # never really send; tests read the messages from `outbox`
    yield application
    drop_database(TEST_DB)


@pytest.fixture
def outbox(app):
    """Emails the app tried to send during this test (flask_mail.Message objects)."""
    sent = []
    def record(message, app):
        sent.append(message)
    email_dispatched.connect(record)
    yield sent
    email_dispatched.disconnect(record)


def code_in(message):
    return re.search(r"\b(\d{6})\b", message.body).group(1)


def logged_in(app, user_id, name, admin=False):
    c = app.test_client()
    with c.session_transaction() as s:
        s.update(user_id=user_id, user_name=name, is_admin=admin, csrf=CSRF)
    return c


@pytest.fixture
def anon(app):
    """A visitor who isn't logged in (with a known CSRF token for form posts)."""
    c = app.test_client()
    with c.session_transaction() as s:
        s["csrf"] = CSRF
    return c


@pytest.fixture
def admin(app):
    uid = q("SELECT id FROM users WHERE email=%s", ("admin@test.local",))[0]["id"]
    return logged_in(app, uid, "Admin", admin=True)


def make_customer(email=None, password="secret-pass", name="Cust"):
    email = email or f"cust-{uuid.uuid4().hex[:8]}@test.local"
    c = connect()
    cur = c.cursor()
    cur.execute("INSERT INTO users(name,email,phone,password_hash) VALUES(%s,%s,'',%s)", (name, email, generate_password_hash(password)))
    uid = cur.lastrowid
    c.close()
    return uid, email


@pytest.fixture
def customer(app):
    uid, _ = make_customer()
    return logged_in(app, uid, "Cust")


# ---------- inventory helpers (go through the admin API, like a real admin would) ----------
def ingredients(admin_client):
    return {i["name"]: i for i in admin_client.get("/admin/api/ingredients").get_json()}


def set_stock(admin_client, name, stock):
    ing = ingredients(admin_client)[name]
    r = admin_client.put(f"/admin/api/ingredients/{ing['id']}", json={**ing, "stock": stock}, headers=H)
    assert r.status_code == 200, r.get_json()


def stock(name):
    return float(q("SELECT stock FROM ingredients WHERE name=%s", (name,))[0]["stock"])


def place_order(client, items, payment="cash", **extra):
    body = {"items": items, "order_type": "dine-in", "payment": payment, **extra}
    return client.post("/api/orders", json=body, headers=H)
