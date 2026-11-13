"""Pages load, and the database sets itself up (once) from an empty database."""
import os, subprocess, sys
from werkzeug.exceptions import Forbidden, RequestEntityTooLarge
from conftest import TEST_DB, connect, drop_database, q

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_public_and_customer_pages(anon, customer):
    assert anon.get("/").status_code == 200
    login = anon.get("/login")
    assert login.status_code == 200 and b"auth-layout--customer" in login.data and b'href="/register"' in login.data
    assert b"<nav>" not in login.data
    admin_login = anon.get("/admin-login")
    assert admin_login.status_code == 200 and b"auth-layout--admin" in admin_login.data and b"<nav>" not in admin_login.data
    assert anon.get("/register").status_code == 200
    assert anon.get("/healthz").get_data(as_text=True) == "ok"
    for path in ("/menu", "/your-order", "/account"):
        assert customer.get(path).status_code == 200, path


def test_friendly_error_pages_and_api_errors(anon):
    missing = anon.get("/does-not-exist")
    assert missing.status_code == 404 and b"Page not found" in missing.data and b"Back to the home page" in missing.data
    missing_api = anon.get("/admin/api/ingredients")
    assert missing_api.status_code == 404 and missing_api.is_json


def test_friendly_forbidden_upload_and_server_errors(app):
    with app.test_request_context("/_test/forbidden"):
        forbidden = app.make_response(app.handle_http_exception(Forbidden()))
    assert forbidden.status_code == 403 and b"Access denied" in forbidden.data

    with app.test_request_context("/_test/upload"):
        oversized = app.make_response(app.handle_http_exception(RequestEntityTooLarge()))
    assert oversized.status_code == 413 and b"up to 5 MB" in oversized.data

    propagate = app.config["PROPAGATE_EXCEPTIONS"]
    app.config["PROPAGATE_EXCEPTIONS"] = False
    try:
        with app.test_request_context("/_test/failure"):
            failure = app.handle_exception(RuntimeError("internal detail"))
    finally:
        app.config["PROPAGATE_EXCEPTIONS"] = propagate
    assert failure.status_code == 500 and b"Something went wrong" in failure.data
    assert b"internal detail" not in failure.data


def test_admin_pages(admin):
    for path in ("/admin", "/admin/orders", "/admin/orders?status=Received", "/admin/orders?pay=pending",
                 "/admin/inventory", "/admin/menu-items"):
        assert admin.get(path).status_code == 200, path


def test_starter_data_loaded_once(app):
    counts = lambda: tuple(q(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in ("categories", "ingredients", "menu_items", "menu_item_ingredients"))
    assert q("SELECT COUNT(*) AS n FROM menu_items WHERE id IN ('fries','c-latte','f-matcha')")[0]["n"] == 3
    before = counts()
    import cafe
    cafe.create_app()                                                     # a restart doesn't seed again
    assert counts() == before
    assert q("SELECT COUNT(*) AS n FROM users WHERE is_admin=1")[0]["n"] == 1


def run_app_process(env_extra):
    env = {**os.environ, **env_extra}
    return subprocess.Popen([sys.executable, "-c", "from cafe import create_app; create_app()"], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_two_processes_set_up_an_empty_database_once():
    db = TEST_DB + "_lock"
    drop_database(db)
    try:
        procs = [run_app_process({"MYSQL_DATABASE": db}) for _ in range(2)]          # like two gunicorn workers
        results = [p.communicate(timeout=120) for p in procs]
        assert all(p.returncode == 0 for p in procs), results
        assert sum(out.count("Starter menu") for out, _ in results) == 1
        c = connect(db); cur = c.cursor()
        cur.execute("SELECT (SELECT COUNT(*) FROM categories), (SELECT COUNT(*) FROM menu_items), (SELECT COUNT(*) FROM users WHERE is_admin=1)")
        assert cur.fetchone() == (4, 15, 1)
        c.close()
    finally:
        drop_database(db)


def test_production_needs_secret_key_and_admin_password():
    p = run_app_process({"APP_ENV": "production", "SECRET_KEY": ""})
    _, err = p.communicate(timeout=60)
    assert p.returncode != 0 and "SECRET_KEY is not set" in err

    db = TEST_DB + "_prod"
    drop_database(db)
    c = connect(None); c.cursor().execute(f"CREATE DATABASE `{db}`"); c.close()       # production never creates the database itself
    try:
        p = run_app_process({"APP_ENV": "production", "SECRET_KEY": "x" * 64, "MYSQL_DATABASE": db, "ADMIN_PASSWORD": ""})
        _, err = p.communicate(timeout=120)
        assert p.returncode != 0 and "There is no admin account yet" in err
        p = run_app_process({"APP_ENV": "production", "SECRET_KEY": "x" * 64, "MYSQL_DATABASE": db, "ADMIN_PASSWORD": "a-strong-one"})
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0, err
    finally:
        drop_database(db)
