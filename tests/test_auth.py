"""Registration, login (with the emailed code), admin login, password reset, logout and protected pages."""
from conftest import CSRF, code_in, make_customer, q


def form(**fields):
    return {"csrf": CSRF, **fields}


def test_register_sends_code_and_verify_creates_account(anon, outbox):
    r = anon.post("/register", data=form(name="New Person", email="New@Test.local", password="hunter22"))
    assert r.status_code == 302 and "/verify" in r.location
    assert len(outbox) == 1 and outbox[0].recipients == ["new@test.local"]
    assert not q("SELECT 1 FROM users WHERE email='new@test.local'")          # not created until the code is entered

    r = anon.post("/verify", data=form(code="000000"))
    assert b"Incorrect code" in r.data
    r = anon.post("/verify", data=form(code=code_in(outbox[0])))
    assert r.status_code == 302 and r.location.endswith("/account")
    user = q("SELECT name, password_hash FROM users WHERE email='new@test.local'")[0]
    assert user["name"] == "New Person" and "hunter22" not in user["password_hash"]   # stored hashed
    assert anon.get("/account").status_code == 200


def test_register_rejects_short_password_and_duplicate_email(anon, outbox):
    r = anon.post("/register", data=form(name="X", email="short@test.local", password="12345"))
    assert b"at least 6 characters" in r.data and not outbox
    _, email = make_customer()
    r = anon.post("/register", data=form(name="X", email=email, password="longenough"))
    assert b"already registered" in r.data and not outbox


def test_login_with_code(anon, outbox):
    _, email = make_customer(password="right-pass")
    r = anon.post("/login?next=/menu", data=form(email=email.upper(), password="right-pass"))
    assert r.status_code == 302 and "/verify" in r.location
    r = anon.post("/verify?next=/menu", data=form(code=code_in(outbox[0])))
    assert r.status_code == 302 and r.location.endswith("/menu")
    assert anon.get("/menu").status_code == 200


def test_login_wrong_password_or_unknown_email(anon, outbox):
    _, email = make_customer(password="right-pass")
    for e, p in [(email, "wrong-pass"), ("nobody@test.local", "whatever")]:
        r = anon.post("/login", data=form(email=e, password=p))
        assert r.status_code == 200 and b"Wrong email or password." in r.data
    assert not outbox


def test_admin_cannot_use_customer_login_and_customer_cannot_use_admin_login(anon, outbox):
    r = anon.post("/login", data=form(email="admin@test.local", password="admin-pass-123"))
    assert b"Wrong email or password." in r.data and not outbox
    _, email = make_customer(password="cust-pass")
    r = anon.post("/admin-login", data=form(email=email, password="cust-pass"))
    assert b"Wrong email or password." in r.data


def test_admin_login(anon):
    r = anon.post("/admin-login", data=form(email="admin@test.local", password="admin-pass-123"))
    assert r.status_code == 302 and r.location.endswith("/admin")
    assert anon.get("/admin").status_code == 200


def test_protected_pages_redirect_to_login(anon):
    for path in ("/menu", "/your-order", "/account"):
        r = anon.get(path)
        assert r.status_code == 302 and "/login" in r.location and "next=" in r.location
    assert anon.get("/admin").status_code == 302                                 # admin pages -> admin login
    assert anon.get("/admin/api/ingredients").status_code == 404                  # admin API hides itself


def test_admin_cannot_open_customer_pages_or_order(admin):
    assert admin.get("/menu").status_code == 302
    r = admin.post("/api/orders", json={}, headers={"X-CSRFToken": CSRF})
    assert r.status_code == 403 and r.get_json()["error"] == "Admins cannot place orders"


def test_logout(customer):
    assert customer.get("/account").status_code == 200
    r = customer.post("/logout", data=form())
    assert r.status_code == 302 and r.location.endswith("/")
    assert customer.get("/account").status_code == 302


def test_post_without_csrf_is_refused(anon):
    r = anon.post("/login", data={"email": "a@b.c", "password": "x"})
    assert r.status_code == 400


def test_forgot_and_reset_password(anon, outbox):
    _, email = make_customer(password="old-pass")
    r = anon.post("/forgot", data=form(email=email))
    assert r.status_code == 302 and r.location.endswith("/reset") and len(outbox) == 1
    r = anon.post("/reset", data=form(code=code_in(outbox[0]), password="new-pass-1", confirm="different"))
    assert b"don&#39;t match" in r.data or b"don't match" in r.data
    r = anon.post("/reset", data=form(code=code_in(outbox[0]), password="new-pass-1", confirm="new-pass-1"))
    assert r.status_code == 302 and r.location.endswith("/login")
    outbox.clear()
    r = anon.post("/login", data=form(email=email, password="new-pass-1"))
    assert r.status_code == 302 and len(outbox) == 1                             # new password accepted


def test_forgot_for_unknown_email_reveals_nothing(anon, outbox):
    r = anon.post("/forgot", data=form(email="ghost@test.local"))
    assert r.status_code == 302 and r.location.endswith("/reset") and not outbox
