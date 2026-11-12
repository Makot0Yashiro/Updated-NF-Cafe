"""Customer menu, placing orders (stock deduction) and the stock rules for status / payment changes."""
import json
import threading
from conftest import H, CSRF, ingredients, logged_in, make_customer, place_order, q, set_stock, stock


def status(admin, order_id, s):
    return admin.post(f"/admin/api/orders/{order_id}/status", json={"status": s}, headers=H)


def pay(admin, order_id, action):
    return admin.post(f"/admin/api/orders/{order_id}/payment", json={"action": action}, headers=H)


# ---------- customer menu ----------
def test_menu_shows_groups_sold_out_and_hides_inactive(admin, customer):
    set_stock(admin, "Tomatoes", 0)                       # Burger and Salad need tomatoes
    items = {i["id"]: i for i in admin.get("/admin/api/menu-items").get_json()["items"]}
    admin.put("/admin/api/menu-items/salad", json={**items["salad"], "active": False}, headers=H)
    html = customer.get("/menu").get_data(as_text=True)
    assert "Food" in html and "Beverages" in html and 'data-id="c-latte"' in html
    assert 'aria-label="Burger, sold out"' in html
    assert 'data-id="salad"' not in html                 # hidden item isn't shown
    admin.put("/admin/api/menu-items/salad", json={**items["salad"], "active": True}, headers=H)


# ---------- placing orders ----------
def test_order_takes_exact_stock_and_records_it(admin, customer):
    set_stock(admin, "Potatoes", 5000); set_stock(admin, "Espresso beans", 1000)
    before = {n: stock(n) for n in ("Potatoes", "Cooking oil", "Salt", "Espresso beans", "Fresh milk")}
    r = place_order(customer, [{"id": "fries", "qty": 2}, {"id": "c-latte", "qty": 1}])
    assert r.status_code == 201
    taken = {n: before[n] - stock(n) for n in before}
    assert taken == {"Potatoes": 400, "Cooking oil": 60, "Salt": 4, "Espresso beans": 18, "Fresh milk": 200}
    row = q("SELECT items_json, total, stock_json, status FROM orders WHERE id=%s", (r.get_json()["id"],))[0]
    ids = {n: i["id"] for n, i in ingredients(admin).items()}
    assert {int(k): float(v) for k, v in json.loads(row["stock_json"]).items()} == {ids[n]: float(v) for n, v in taken.items()}
    assert json.loads(row["items_json"])[0] == {"id": "fries", "name": "Fries", "cat": "Food", "price": 99.0, "qty": 2}
    assert row["total"] == 318 and row["status"] == "Received"


def test_order_refused_when_short_and_stock_unchanged(admin, customer):
    set_stock(admin, "Tomatoes", 0); set_stock(admin, "Cheese sauce", 400)       # 400 / 60 per Nachos = 6 servings
    buns, sauce = stock("Burger buns"), stock("Cheese sauce")
    r = place_order(customer, [{"id": "burger", "qty": 1}])
    assert r.status_code == 409 and r.get_json()["error"] == "Sorry, Burger is sold out"
    r = place_order(customer, [{"id": "nachos", "qty": 7}])
    assert r.status_code == 409 and r.get_json()["error"] == "Only 6 Nachos left"
    r = place_order(customer, [{"id": "nachos", "qty": 4}, {"id": "nachos", "qty": 3}])   # fits per line, not together
    assert r.status_code == 409 and "Cheese sauce" in r.get_json()["error"]
    assert stock("Burger buns") == buns and stock("Cheese sauce") == sauce


def test_order_validation(admin, customer):
    assert place_order(customer, []).get_json()["error"] == "Your order is empty"
    assert place_order(customer, [{"id": "nope", "qty": 1}]).status_code == 400
    assert place_order(customer, [{"id": "fries", "qty": 0}]).status_code == 400
    r = place_order(customer, [{"id": "fries", "qty": 1}], payment="online", ref="")
    assert r.status_code == 400 and "reference number" in r.get_json()["error"]
    r = customer.post("/api/orders", json={"items": [{"id": "fries", "qty": 1}], "order_type": "delivery", "payment": "cash"}, headers=H)
    assert r.status_code == 400 and "delivery address" in r.get_json()["error"]


def test_inactive_item_cannot_be_ordered(admin, customer):
    items = {i["id"]: i for i in admin.get("/admin/api/menu-items").get_json()["items"]}
    admin.put("/admin/api/menu-items/c-americano", json={**items["c-americano"], "active": False}, headers=H)
    assert place_order(customer, [{"id": "c-americano", "qty": 1}]).status_code == 400
    admin.put("/admin/api/menu-items/c-americano", json={**items["c-americano"], "active": True}, headers=H)


def test_customer_sees_and_tracks_own_orders_only(app, admin, customer):
    set_stock(admin, "Potatoes", 5000)
    oid = place_order(customer, [{"id": "fries", "qty": 1}]).get_json()["id"]
    mine = customer.get("/api/orders").get_json()
    assert mine[0]["id"] == oid and mine[0]["status"] == "Received" and mine[0]["items"][0]["name"] == "Fries"
    assert customer.get(f"/api/orders/{oid}/track").get_json()["id"] == oid
    assert customer.get("/your-order").status_code == 200
    other_uid, _ = make_customer()
    assert logged_in(app, other_uid, "Other").get(f"/api/orders/{oid}/track").status_code == 404


# ---------- status / payment changes and stock ----------
def test_cancel_at_received_returns_stock_once_and_reopen_takes_it_again(admin, customer):
    set_stock(admin, "Potatoes", 5000)
    oid = place_order(customer, [{"id": "fries", "qty": 2}]).get_json()["id"]
    assert stock("Potatoes") == 4600
    assert status(admin, oid, "Cancelled").status_code == 200 and stock("Potatoes") == 5000
    status(admin, oid, "Cancelled")
    assert stock("Potatoes") == 5000                                          # not returned twice
    r = status(admin, oid, "Received")
    assert r.status_code == 200 and stock("Potatoes") == 4600
    assert q("SELECT stock_returned FROM orders WHERE id=%s", (oid,))[0]["stock_returned"] == 0


def test_cancel_after_preparing_keeps_stock_used(admin, customer):
    set_stock(admin, "Potatoes", 5000)
    oid = place_order(customer, [{"id": "fries", "qty": 1}]).get_json()["id"]
    status(admin, oid, "Preparing"); status(admin, oid, "Cancelled")
    assert stock("Potatoes") == 4800


def test_rejected_payment_returns_stock_and_confirm_takes_it_again(admin, customer):
    set_stock(admin, "Potatoes", 5000)
    oid = place_order(customer, [{"id": "fries", "qty": 1}], payment="online", ref="ABCD1234").get_json()["id"]
    assert pay(admin, oid, "reject").status_code == 200 and stock("Potatoes") == 5000
    pay(admin, oid, "reject")
    assert stock("Potatoes") == 5000
    r = pay(admin, oid, "confirm")
    assert r.status_code == 200 and r.get_json()["pay_status"] == "paid" and stock("Potatoes") == 4800


def test_reopen_refused_when_stock_is_gone(admin, customer):
    set_stock(admin, "Potatoes", 5000)
    oid = place_order(customer, [{"id": "fries", "qty": 1}]).get_json()["id"]
    status(admin, oid, "Cancelled")
    set_stock(admin, "Potatoes", 0)
    r = status(admin, oid, "Received")
    assert r.status_code == 409 and "Potatoes" in r.get_json()["error"]
    assert q("SELECT status FROM orders WHERE id=%s", (oid,))[0]["status"] == "Cancelled" and stock("Potatoes") == 0


def test_invalid_status_or_payment_action(admin, customer):
    set_stock(admin, "Potatoes", 5000)
    oid = place_order(customer, [{"id": "fries", "qty": 1}]).get_json()["id"]
    assert status(admin, oid, "Delivered").status_code == 400                # dine-in orders never get "Delivered"
    assert pay(admin, oid, "maybe").status_code == 400
    assert status(admin, 999999, "Ready").status_code == 400


def test_order_from_before_inventory_tracking_changes_without_touching_stock(admin):
    uid, _ = make_customer()
    q("""INSERT INTO orders(user_id,customer_name,order_type,payment,note,items_json,subtotal,coupon,discount,total,status,status_at,created_at)
         VALUES(%s,'Old','pickup','cash','',%s,99,'',0,99,'Received','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')""",
      (uid, json.dumps([{"id": "fries", "name": "Fries", "cat": "Food", "price": 99, "qty": 1}])))
    oid = q("SELECT MAX(id) AS id FROM orders")[0]["id"]
    potatoes = stock("Potatoes")
    assert status(admin, oid, "Cancelled").status_code == 200 and stock("Potatoes") == potatoes
    assert f'data-id="{oid}"'.encode() in admin.get("/admin/orders").data


def test_two_orders_for_the_last_serving(app, admin):
    set_stock(admin, "Espresso beans", 18)                                    # exactly one Americano
    uid, _ = make_customer()
    codes, gate = [], threading.Barrier(2)
    def order():
        c = logged_in(app, uid, "Cust")
        gate.wait()
        codes.append(place_order(c, [{"id": "c-americano", "qty": 1}]).status_code)
    threads = [threading.Thread(target=order) for _ in range(2)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert sorted(codes) == [201, 409] and stock("Espresso beans") == 0
