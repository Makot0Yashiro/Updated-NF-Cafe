import json, re
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, session, render_template, abort
from ..db import get_db
from ..auth_utils import login_required, check_csrf
from ..menu_data import COUPONS, CAFE_LOCATION
from .. import catalog
from ..stock import take_for_order, on_order_change, OutOfStock

bp = Blueprint("orders", __name__)
TRIP_SECONDS = 120   # how long the courier marker takes to move from the cafe to the customer (demo animation)


def stages(order_type):
    base = ["Received", "Preparing", "Ready"]
    return base + (["Out for delivery", "Delivered"] if order_type == "delivery" else ["Completed"])


def now():
    return datetime.now(timezone.utc)


def locate(row):
    """Where the order is: at the cafe, moving to the customer once 'Out for delivery', then at the customer."""
    lat, lng = CAFE_LOCATION
    if row["order_type"] == "delivery" and row["dest_lat"] is not None:
        if row["status"] == "Delivered":
            return row["dest_lat"], row["dest_lng"]
        if row["status"] == "Out for delivery":
            since = datetime.fromisoformat(row["status_at"] or row["created_at"])
            p = min(max((now() - since).total_seconds() / TRIP_SECONDS, 0), 1)
            return lat + (row["dest_lat"] - lat) * p, lng + (row["dest_lng"] - lng) * p
    return lat, lng


def refresh(row):
    lat, lng = locate(row)
    if row["cur_lat"] != lat or row["cur_lng"] != lng:
        db = get_db()
        db.execute("UPDATE orders SET cur_lat=?, cur_lng=? WHERE id=?", (lat, lng, row["id"]))
        db.commit()
        row = db.execute("SELECT * FROM orders WHERE id=?", (row["id"],)).fetchone()
    return row


def _change_order(order_id, status=None, pay_status=None):
    """Save a status or payment change together with its stock effect (stock.on_order_change), in one transaction.
    Returns the updated row, None if the change isn't valid, and raises OutOfStock if reopening the order needs stock that's gone."""
    db = get_db()
    db.commit()                                   # start a fresh transaction so FOR UPDATE sees the latest row
    row = db.execute("SELECT * FROM orders WHERE id=? FOR UPDATE", (order_id,)).fetchone()
    if not row or (status is not None and status not in stages(row["order_type"]) + ["Cancelled"]) or \
            (pay_status is not None and pay_status not in ("paid", "rejected")):
        db.rollback()
        return None
    try:
        returned = on_order_change(db, row, status or row["status"], pay_status or row["pay_status"])
        if status is not None:
            db.execute("UPDATE orders SET status=?, status_at=?, stock_returned=? WHERE id=?", (status, now().isoformat(), returned, order_id))
        else:
            db.execute("UPDATE orders SET pay_status=?, pay_at=?, stock_returned=? WHERE id=?", (pay_status, now().isoformat(), returned, order_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()


def set_status(order_id, status):
    """Used by the admin. Returns the updated row, or None if the status is not valid for that order. May raise OutOfStock."""
    row = _change_order(order_id, status=status)
    return refresh(row) if row else None


def set_payment(order_id, pay_status):
    """Admin: mark an order's payment as 'paid' or 'rejected'. Returns the updated row (or None). May raise OutOfStock."""
    return _change_order(order_id, pay_status=pay_status)


def public_order(r):
    return {"id": r["id"], "status": r["status"], "order_type": "pickup" if r["order_type"] == "takeaway" else r["order_type"],
            "payment": "cash" if r["payment"] == "cash" else "online", "pay_status": r["pay_status"] or "unpaid", "pay_ref": r["pay_ref"] or "",
            "address": r["dest_address"] or "", "total": r["total"], "created_at": r["created_at"], "customer": r["customer_name"],
            "note": r["note"], "items": json.loads(r["items_json"]), "lat": r["cur_lat"], "lng": r["cur_lng"],
            "dest": [r["dest_lat"], r["dest_lng"]] if r["dest_lat"] is not None else None, "steps": stages(r["order_type"])}


def _own(order_id):
    r = get_db().execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, session["user_id"])).fetchone()
    return r or abort(404)


@bp.get("/your-order")
@login_required
def your_order():
    rows = get_db().execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    return render_template("order.html", orders=[public_order(refresh(r)) for r in rows], cafe=CAFE_LOCATION)


@bp.post("/api/orders")
@login_required
def create_order():
    check_csrf()
    d = request.get_json(silent=True) or {}
    lines, stock_lines, subtotal = [], [], 0
    wanted = [it for it in d.get("items", []) if isinstance(it, dict)]
    menu = {r["id"]: r for r in catalog.items([str(it.get("id")) for it in wanted], active_only=True)} if wanted else {}
    for it in wanted:
        item = menu.get(str(it.get("id")))
        try:
            qty = int(it.get("qty", 0))
        except (TypeError, ValueError):
            qty = 0
        if not item:
            return jsonify(error="An item in your order is no longer on the menu. Please refresh the page."), 400
        if not 0 < qty <= 50:
            return jsonify(error="Invalid item"), 400
        price = catalog.num(item["price"])        # price always comes from the server
        lines.append({"id": item["id"], "name": item["name"], "cat": item["cat_name"], "price": price, "qty": qty})
        stock_lines.append((item, qty))
        subtotal = round(subtotal + price * qty, 2)
    if not lines:
        return jsonify(error="Your order is empty"), 400
    otype = d.get("order_type")
    if otype not in ("dine-in", "pickup", "delivery"):
        return jsonify(error="Choose an order type"), 400
    payment = d.get("payment")
    if payment not in ("cash", "online"):
        return jsonify(error="Choose how you'd like to pay"), 400
    ref = re.sub(r"[^\w\-]", "", str(d.get("ref", "")))[:40]
    if payment == "online" and len(ref) < 4:
        return jsonify(error="Enter the reference number from your payment receipt"), 400
    address = str(d.get("address", "")).strip()[:200]
    if otype == "delivery" and not address:
        return jsonify(error="Please enter your delivery address"), 400
    code = (d.get("coupon") or "").upper()
    discount = round(subtotal * COUPONS.get(code, 0), 2)
    dlat = dlng = None
    if otype == "delivery":
        try:
            dlat, dlng = float(d["dest_lat"]), float(d["dest_lng"])
            assert -90 <= dlat <= 90 and -180 <= dlng <= 180
        except Exception:                         # no location shared -> ~1.5 km from the cafe
            dlat, dlng = CAFE_LOCATION[0] + 0.012, CAFE_LOCATION[1] + 0.010
    db = get_db()
    ts = now().isoformat()
    try:                                          # stock + order in one transaction: both happen or neither does
        stock_json = take_for_order(db, stock_lines)
        cur = db.execute(
            "INSERT INTO orders(user_id,customer_name,order_type,payment,note,items_json,subtotal,coupon,discount,total,status,status_at,"
            "dest_lat,dest_lng,dest_address,cur_lat,cur_lng,pay_status,pay_ref,created_at,stock_json,stock_returned) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (session["user_id"], session["user_name"], otype, payment, str(d.get("note", ""))[:200], json.dumps(lines), subtotal,
             code if discount else "", discount, round(subtotal - discount, 2), "Received", ts, dlat, dlng, address if otype == "delivery" else None,
             CAFE_LOCATION[0], CAFE_LOCATION[1], "pending" if payment == "online" else "unpaid", ref if payment == "online" else None, ts, stock_json))
        db.commit()
    except OutOfStock as e:
        db.rollback()
        return jsonify(error=str(e)), 409
    except Exception:
        db.rollback()
        raise
    return jsonify(id=cur.lastrowid), 201


@bp.get("/api/orders")
@login_required
def list_orders():
    rows = get_db().execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    return jsonify([public_order(refresh(r)) for r in rows])


@bp.get("/api/orders/<int:order_id>/track")
@login_required
def track(order_id):
    return jsonify(public_order(refresh(_own(order_id))))
