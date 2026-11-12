"""Stock changes: taking ingredients out when an order is placed, and giving them back when it's cancelled / its payment rejected.
Every function here runs inside the caller's transaction; the caller commits or rolls back."""
import json
from collections import defaultdict
from decimal import Decimal


class OutOfStock(Exception):
    """Not enough stock; str(e) is a message for humans."""


def _lock(db, ids):
    """Lock the ingredient rows (in id order, so two orders can't deadlock) and return {id: {name, stock}}."""
    ids = sorted(set(ids))
    if not ids:
        return {}
    rows = db.execute(f"SELECT id, name, stock FROM ingredients WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id FOR UPDATE", tuple(ids)).fetchall()
    return {r["id"]: r for r in rows}


def _subtract(db, need):
    for ing_id, amount in need.items():
        db.execute("UPDATE ingredients SET stock = stock - ? WHERE id=?", (amount, ing_id))


def take_for_order(db, lines):
    """lines = [(item row with "recipe" from catalog.items(), quantity)].
    Takes the ingredients out of stock and returns the stock_json to store on the order. Raises OutOfStock."""
    need = defaultdict(Decimal)
    for item, qty in lines:
        if not item["recipe"]:
            raise OutOfStock(f"Sorry, {item['name']} is not available right now")
        for r in item["recipe"]:
            need[r["ingredient_id"]] += r["qty"] * qty
    stock = _lock(db, need)
    for item, qty in lines:                         # name the item that can't be made
        can = min(int(stock[r["ingredient_id"]]["stock"] // r["qty"]) if r["ingredient_id"] in stock else 0 for r in item["recipe"])
        if can < qty:
            raise OutOfStock(f"Sorry, {item['name']} is sold out" if can <= 0 else f"Only {can} {item['name']} left")
    short = [stock[i]["name"] for i, amount in need.items() if stock[i]["stock"] < amount]
    if short:                                       # each item fits on its own, but together they share an ingredient
        raise OutOfStock(f"Not enough {', '.join(short)} for this whole order. Try fewer items.")
    _subtract(db, need)
    return json.dumps({str(i): str(a) for i, a in need.items()})


def _amounts(order):
    return {int(i): Decimal(a) for i, a in json.loads(order["stock_json"]).items()}


def return_for_order(db, order):
    for ing_id, amount in _amounts(order).items():   # an ingredient deleted since then is simply skipped
        db.execute("UPDATE ingredients SET stock = stock + ? WHERE id=?", (amount, ing_id))


def retake_for_order(db, order):
    need = _amounts(order)
    stock = _lock(db, need)
    need = {i: a for i, a in need.items() if i in stock}
    short = [stock[i]["name"] for i, a in need.items() if stock[i]["stock"] < a]
    if short:
        raise OutOfStock(f"Not enough {', '.join(short)} in stock to reopen order #{order['id']}.")
    _subtract(db, need)


def holds_stock(status, pay_status):
    return status != "Cancelled" and pay_status != "rejected"


def on_order_change(db, order, status, pay_status):
    """Call before saving a status / payment change. `order` is the row as it is now (locked FOR UPDATE).
    - Stops holding stock while still 'Received'  -> give the ingredients back (once).
    - Stops holding stock later (Preparing...)     -> keep them used; the food is assumed made.
    - Holds stock again after they were given back -> take them again, or raise OutOfStock.
    Returns the stock_returned value to save."""
    returned = order["stock_returned"] or 0
    if not order["stock_json"]:                     # placed before inventory tracking existed
        return returned
    was, now = holds_stock(order["status"], order["pay_status"]), holds_stock(status, pay_status)
    if was and not now and order["status"] == "Received" and not returned:
        return_for_order(db, order)
        return 1
    if now and not was and returned:
        retake_for_order(db, order)
        return 0
    return returned
