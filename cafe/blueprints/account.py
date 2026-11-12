from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from ..db import get_db, IntegrityError
from ..auth_utils import login_required, check_csrf
from ..menu_data import CAFE_LOCATION

bp = Blueprint("account", __name__)
PAY = {"cash": "Cash", "online": "Online payment (QR)"}


def profile(uid):
    r = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return {"name": r["name"], "email": r["email"], "phone": r["phone"] or "", "address": r["address"] or "",
            "lat": r["addr_lat"], "lng": r["addr_lng"], "pay_method": "cash" if (r["pay_method"] or "cash") == "cash" else "online",
            "pay_account": r["pay_account"] or ""}


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
        if not name or "@" not in email:
            flash("Please enter a username and a valid email.")
        else:
            try:
                db = get_db()
                db.execute("UPDATE users SET name=?,email=?,phone=?,address=?,addr_lat=?,addr_lng=?,pay_method=?,pay_account=? WHERE id=?",
                           (name[:60], email, f.get("phone", "").strip()[:25], f.get("address", "").strip()[:200],
                            _num(f.get("lat"), 90), _num(f.get("lng"), 180), pay, f.get("pay_account", "").strip()[:25], session["user_id"]))
                db.commit()
                session["user_name"] = name[:60]
                flash("Your account has been saved.")
            except IntegrityError:
                flash("That email is already used by another account.")
        return redirect(url_for("account.account"))
    return render_template("account.html", me=profile(session["user_id"]), pay=PAY, cafe=CAFE_LOCATION)
