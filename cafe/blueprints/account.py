from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from ..db import get_db, IntegrityError
from ..auth_utils import login_required, check_csrf, valid_email
from ..menu_data import CAFE_LOCATION
from ..models import Customer
from ..repositories import UserRepository

bp = Blueprint("account", __name__)
PAY = {"cash": "Cash", "online": "Online payment (QR)"}


def profile(uid):
    customer = UserRepository(get_db()).get(uid)
    if not isinstance(customer, Customer):
        return {}
    return {"name": customer.name, "email": customer.email, "phone": customer.phone, "address": customer.address,
            "lat": customer.addr_lat, "lng": customer.addr_lng,
            "pay_method": "cash" if customer.pay_method == "cash" else "online", "pay_account": customer.pay_account}


def _num(v, lim):
    try:
        v = float(v)
        return v if -lim <= v <= lim else None
    except (TypeError, ValueError):
        return None


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        check_csrf()
        f = request.form
        name, email = f.get("name", "").strip(), f.get("email", "").strip().lower()
        pay = f.get("pay_method") if f.get("pay_method") in PAY else "cash"
        if not name or not valid_email(email):
            flash("Please enter a username and a valid email.")
        else:
            try:
                db = get_db()
                UserRepository(db).update_profile(
                    session["user_id"], name=name[:60], email=email, phone=f.get("phone", "").strip()[:25],
                    address=f.get("address", "").strip()[:200], addr_lat=_num(f.get("lat"), 90),
                    addr_lng=_num(f.get("lng"), 180), pay_method=pay, pay_account=f.get("pay_account", "").strip()[:25])
                db.commit()
                session["user_name"] = name[:60]
                flash("Your account has been saved.")
            except IntegrityError:
                flash("That email is already used by another account.")
        return redirect(url_for("account.account"))
    return render_template("account.html", me=profile(session["user_id"]), pay=PAY, cafe=CAFE_LOCATION)
