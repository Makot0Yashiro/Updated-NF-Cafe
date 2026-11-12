"""Profile management (/account)."""
from conftest import CSRF, logged_in, make_customer, q


def test_view_and_update_profile(app):
    uid, email = make_customer(name="Before")
    c = logged_in(app, uid, "Before")
    assert b"Before" in c.get("/account").data
    r = c.post("/account", data={"csrf": CSRF, "name": "After", "email": email, "phone": "0917 000 0000",
                                 "address": "1 Rizal St", "lat": "14.28", "lng": "121.41", "pay_method": "online", "pay_account": "0917"})
    assert r.status_code == 302
    row = q("SELECT name, phone, address, addr_lat, pay_method, pay_account FROM users WHERE id=%s", (uid,))[0]
    assert row == {"name": "After", "phone": "0917 000 0000", "address": "1 Rizal St", "addr_lat": 14.28, "pay_method": "online", "pay_account": "0917"}
    assert b"Your account has been saved." in c.get("/account").data


def test_profile_validation(app):
    uid, email = make_customer()
    _, other = make_customer()
    c = logged_in(app, uid, "Cust")
    c.post("/account", data={"csrf": CSRF, "name": "", "email": email})
    assert b"Please enter a username and a valid email." in c.get("/account").data
    c.post("/account", data={"csrf": CSRF, "name": "X", "email": other})
    assert b"That email is already used by another account." in c.get("/account").data
    assert q("SELECT email FROM users WHERE id=%s", (uid,))[0]["email"] == email
