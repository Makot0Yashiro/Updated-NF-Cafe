"""Stock changes: taking ingredients out when an order is placed, and giving them back when it's cancelled / its payment rejected.
Every function here runs inside the caller's transaction; the caller commits or rolls back."""
import json
from collections import defaultdict
from decimal import Decimal


class OutOfStock(Exception):
    """Not enough stock; str(e) is a message for humans."""


class StockService:
    @staticmethod
    def _lock(db, ids):
        """Lock ingredient rows in id order so concurrent orders cannot deadlock."""
        ids = sorted(set(ids))
        if not ids:
            return {}
        rows = db.execute(f"SELECT id, name, stock FROM ingredients WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id FOR UPDATE",
                          tuple(ids)).fetchall()
        return {row["id"]: row for row in rows}

    @staticmethod
    def _subtract(db, need):
        for ingredient_id, amount in need.items():
            db.execute("UPDATE ingredients SET stock=stock-? WHERE id=?", (amount, ingredient_id))

    @classmethod
    def take_for_order(cls, db, lines):
        """Take recipe ingredients for an order and return the stock amounts to persist."""
        need = defaultdict(Decimal)
        for item, quantity in lines:
            if not item["recipe"]:
                raise OutOfStock(f"Sorry, {item['name']} is not available right now")
            for recipe in item["recipe"]:
                need[recipe["ingredient_id"]] += recipe["qty"] * quantity
        stock = cls._lock(db, need)
        for item, quantity in lines:
            can_make = min(int(stock[recipe["ingredient_id"]]["stock"] // recipe["qty"])
                           if recipe["ingredient_id"] in stock else 0 for recipe in item["recipe"])
            if can_make < quantity:
                raise OutOfStock(f"Sorry, {item['name']} is sold out" if can_make <= 0 else f"Only {can_make} {item['name']} left")
        short = [stock[identity]["name"] for identity, amount in need.items() if stock[identity]["stock"] < amount]
        if short:
            raise OutOfStock(f"Not enough {', '.join(short)} for this whole order. Try fewer items.")
        cls._subtract(db, need)
        return json.dumps({str(identity): str(amount) for identity, amount in need.items()})

    @staticmethod
    def _amounts(order):
        return {int(identity): Decimal(amount) for identity, amount in json.loads(order["stock_json"]).items()}

    @classmethod
    def return_for_order(cls, db, order):
        for ingredient_id, amount in cls._amounts(order).items():
            db.execute("UPDATE ingredients SET stock=stock+? WHERE id=?", (amount, ingredient_id))

    @classmethod
    def retake_for_order(cls, db, order):
        need = cls._amounts(order)
        stock = cls._lock(db, need)
        need = {identity: amount for identity, amount in need.items() if identity in stock}
        short = [stock[identity]["name"] for identity, amount in need.items() if stock[identity]["stock"] < amount]
        if short:
            raise OutOfStock(f"Not enough {', '.join(short)} in stock to reopen order #{order['id']}.")
        cls._subtract(db, need)

    @staticmethod
    def holds_stock(status, pay_status):
        return status != "Cancelled" and pay_status != "rejected"

    @classmethod
    def on_order_change(cls, db, order, status, pay_status):
        """Apply stock changes before persisting a locked order status/payment update."""
        returned = order["stock_returned"] or 0
        if not order["stock_json"]:
            return returned
        was = cls.holds_stock(order["status"], order["pay_status"])
        now = cls.holds_stock(status, pay_status)
        if was and not now and order["status"] == "Received" and not returned:
            cls.return_for_order(db, order)
            return 1
        if now and not was and returned:
            cls.retake_for_order(db, order)
            return 0
        return returned


def take_for_order(db, lines):
    return StockService.take_for_order(db, lines)


def on_order_change(db, order, status, pay_status):
    return StockService.on_order_change(db, order, status, pay_status)


def return_for_order(db, order):
    return StockService.return_for_order(db, order)


def retake_for_order(db, order):
    return StockService.retake_for_order(db, order)


def holds_stock(status, pay_status):
    return StockService.holds_stock(status, pay_status)
