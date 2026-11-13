from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, session, abort, redirect, url_for
from ..db import get_db
from ..auth_utils import check_csrf
from ..menu_data import CAFE_LOCATION
from ..repositories import OrderRepository, UserRepository
from ..stock import OutOfStock
from .orders import refresh, public_order, set_status, set_payment, stages
import json

bp = Blueprint("admin", __name__)
PH = timezone(timedelta(hours=8))          # Philippine time for dates/analytics
ALL_STATUSES = ["Received", "Preparing", "Ready", "Out for delivery", "Delivered", "Completed", "Cancelled"]


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        user = UserRepository(get_db()).get(session.get("user_id"))
        if not user or not user.is_admin:
            if request.path.startswith("/admin/api/"):
                abort(404)
            session.pop("is_admin", None)
            return redirect(url_for("auth.admin_login")) if "user_id" not in session else abort(404)
        return f(*a, **kw)
    return wrapper


def bars(pairs, sub=None):
    top = max((v for _, v in pairs), default=0) or 1
    return [{"label": l, "value": v, "pct": round(v / top * 100), "sub": (sub or {}).get(l, "")} for l, v in pairs]


@bp.get("/admin")
@admin_required
def dashboard():
    rows = [order.to_record() for order in OrderRepository(get_db()).list()]
    ok = [r for r in rows if r["status"] != "Cancelled" and r["pay_status"] != "rejected"]
    day = lambda r: datetime.fromisoformat(r["created_at"]).astimezone(PH).date()
    today = datetime.now(PH).date()
    sales = sum(r["total"] for r in ok)
    kpi = {"sales": sales, "orders": len(ok), "avg": sales / len(ok) if ok else 0, "topay": sum(1 for r in rows if r["pay_status"] == "pending"),
           "today": sum(r["total"] for r in ok if day(r) == today),
           "active": sum(1 for r in rows if r["status"] not in ("Delivered", "Completed", "Cancelled"))}
    per_day = defaultdict(float)
    qty, rev, cats, pay, typ = Counter(), Counter(), Counter(), Counter(), Counter()
    for r in ok:
        per_day[day(r)] += r["total"]
        pay[r["payment"]] += r["total"]; typ[r["order_type"]] += r["total"]
        for l in json.loads(r["items_json"]):
            qty[l["name"]] += l["qty"]; rev[l["name"]] += l["qty"] * l["price"]
            cats[l.get("cat") or "Other"] += l["qty"] * l["price"]
    days = [today - timedelta(days=n) for n in range(13, -1, -1)]
    return render_template("admin_dashboard.html", kpi=kpi, page="dash",
        daily=bars([(d.strftime("%b %d"), per_day[d]) for d in days]),
        top=bars(rev.most_common(8), {k: f"{v} sold" for k, v in qty.items()}),
        cats=bars(cats.most_common()), pay=bars(pay.most_common()), typ=bars(typ.most_common()),
        status=Counter(r["status"] for r in rows))


@bp.get("/admin/orders")
@admin_required
def orders_page():
    st = request.args.get("status") if request.args.get("status") in ALL_STATUSES else None
    pay = request.args.get("pay") == "pending"
    filters = {"limit": 200, "pending_payment": pay}
    if st:
        filters["status"] = st
    rows = [order.to_record() for order in OrderRepository(get_db()).list(**filters)]
    orders = []
    for r in rows:
        o = public_order(refresh(r))
        o["when"] = datetime.fromisoformat(r["created_at"]).astimezone(PH).strftime("%b %d, %I:%M %p")
        o["choices"] = stages(r["order_type"]) + ["Cancelled"]
        orders.append(o)
    return render_template("admin_orders.html", orders=orders, cafe=CAFE_LOCATION, current=st, pay_filter=pay, statuses=ALL_STATUSES, page="orders")


@bp.get("/admin/api/orders/<int:order_id>/track")
@admin_required
def track(order_id):
    order = OrderRepository(get_db()).get(order_id)
    r = order.to_record() if order else abort(404)
    return jsonify(public_order(refresh(r)))


@bp.post("/admin/api/orders/<int:order_id>/status")
@admin_required
def update_status(order_id):
    check_csrf()
    try:
        r = set_status(order_id, (request.get_json(silent=True) or {}).get("status"))
    except OutOfStock as e:
        return jsonify(error=str(e)), 409
    return jsonify(public_order(r)) if r else (jsonify(error="Invalid status"), 400)


@bp.post("/admin/api/orders/<int:order_id>/payment")
@admin_required
def update_payment(order_id):
    check_csrf()
    action = (request.get_json(silent=True) or {}).get("action")
    pay_status = {"confirm": "paid", "reject": "rejected"}.get(action)
    if pay_status is None:
        return jsonify(error="Choose confirm or reject."), 400
    try:
        r = set_payment(order_id, pay_status)
    except OutOfStock as e:
        return jsonify(error=str(e)), 409
    return jsonify(public_order(r)) if r else (jsonify(error="Invalid payment action"), 400)
