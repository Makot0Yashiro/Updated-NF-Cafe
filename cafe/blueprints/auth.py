import json
from flask import current_app
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from ..db import get_db, IntegrityError
from ..auth_utils import check_csrf
from ..mailer import send_code, resend_code, check_code

bp = Blueprint("auth", __name__)


def _safe(nxt):
    return nxt if nxt and nxt.startswith("/") and not nxt.startswith("//") else url_for("account.account")


def _mask(email):
    name, domain = email.split("@", 1)
    return name[:1] + "***@" + domain


def _begin(email, purpose, payload=None):
    """Email a code and go to the verify page. Returns None (with a message) if that failed."""
    try:
        oid = send_code(email, purpose, payload)
    except Exception:
        current_app.logger.exception("Could not send the verification email")
        flash("We couldn't send the verification email. Please check the SMTP settings and try again.")
        return None
    if oid is None:
        flash("Please wait a few seconds before asking for another code.")
        return None
    session.update(otp_id=oid, otp_email=email, otp_purpose=purpose)
    return redirect(url_for("auth.verify", next=request.args.get("next")))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        check_csrf()
        u = get_db().execute("SELECT * FROM users WHERE email=?", (request.form["email"].strip().lower(),)).fetchone()
        if u and not u["is_admin"] and check_password_hash(u["password_hash"], request.form["password"]):
            resp = _begin(u["email"], "login")
            if resp:
                return resp
        else:
            flash("Wrong email or password.")
    return render_template("auth.html", mode="login")


@bp.route("/admin-login", methods=["GET", "POST"])     # not linked anywhere: staff type the address
def admin_login():
    if request.method == "POST":
        check_csrf()
        u = get_db().execute("SELECT * FROM users WHERE email=?", (request.form["email"].strip().lower(),)).fetchone()
        if u and u["is_admin"] and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear()
            session.update(user_id=u["id"], user_name=u["name"], is_admin=True)
            return redirect(url_for("admin.dashboard"))
        flash("Wrong email or password.")
    return render_template("admin_login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        check_csrf()
        f = request.form
        email = f["email"].strip().lower()
        if len(f["password"]) < 6:
            flash("Password must be at least 6 characters.")
        elif get_db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            flash("That email is already registered.")
        else:
            resp = _begin(email, "register", {"name": f["name"].strip()[:60], "pw": generate_password_hash(f["password"])})
            if resp:
                return resp
    return render_template("auth.html", mode="register")


@bp.route("/verify", methods=["GET", "POST"])
def verify():
    if "otp_id" not in session:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        check_csrf()
        row, err = check_code(session["otp_id"], request.form.get("code", ""))
        if err:
            flash(err)
        else:
            db = get_db()
            if row["purpose"] == "register":
                p = json.loads(row["payload"])
                try:
                    uid = db.execute("INSERT INTO users(name,email,phone,password_hash) VALUES(?,?,?,?)", (p["name"], row["email"], "", p["pw"])).lastrowid
                    db.commit()
                except IntegrityError:
                    flash("That email is already registered.")
                    return redirect(url_for("auth.login"))
                name = p["name"]
            else:
                u = db.execute("SELECT id, name FROM users WHERE email=?", (row["email"],)).fetchone()
                uid, name = u["id"], u["name"]
            session.clear()
            session.update(user_id=uid, user_name=name, is_admin=False)
            return redirect(_safe(request.args.get("next")))
    return render_template("verify.html", email=_mask(session["otp_email"]))


@bp.post("/verify/resend")
def resend():
    check_csrf()
    if "otp_id" not in session:
        return redirect(url_for("auth.login"))
    try:
        oid = resend_code(session["otp_id"])
    except Exception:
        current_app.logger.exception("Could not resend the verification email")
        flash("We couldn't send the email. Please try again.")
        return redirect(url_for("auth.verify", next=request.args.get("next")))
    if oid is False:
        session.pop("otp_id", None)
        flash("That code is no longer valid. Please start again.")
        return redirect(url_for("auth.login"))
    flash("Please wait a few seconds before asking for another code." if oid is None else "We sent you a new code.")
    if oid:
        session["otp_id"] = oid
    return redirect(url_for("auth.verify", next=request.args.get("next")))


def _send_reset(email, replace_id=None):
    """Emails a reset code if the account exists. 0 = no such account (we never reveal that), None = asked again too soon."""
    u = get_db().execute("SELECT is_admin FROM users WHERE email=?", (email,)).fetchone()
    if not u or u["is_admin"]:
        return 0
    return send_code(email, "reset", replace_id=replace_id or None)


@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        check_csrf()
        email = request.form["email"].strip().lower()
        if "@" not in email:
            flash("Please enter a valid email address.")
            return render_template("forgot.html")
        try:
            rid = _send_reset(email)
        except Exception:
            current_app.logger.exception("Could not send the reset email")
            flash("We couldn't send the email. Please check the SMTP settings and try again.")
            return render_template("forgot.html")
        if rid is None:
            flash("Please wait a few seconds before asking for another code.")
            return render_template("forgot.html")
        session.update(reset_id=rid, reset_email=email)
        return redirect(url_for("auth.reset"))
    return render_template("forgot.html")


@bp.route("/reset", methods=["GET", "POST"])
def reset():
    if "reset_email" not in session:
        return redirect(url_for("auth.forgot"))
    if request.method == "POST":
        check_csrf()
        f = request.form
        if len(f["password"]) < 6:
            flash("Password must be at least 6 characters.")
        elif f["password"] != f["confirm"]:
            flash("The two passwords don't match.")
        else:
            row, err = check_code(session["reset_id"], f.get("code", "")) if session.get("reset_id") else (None, True)
            if err or row["purpose"] != "reset" or row["email"] != session["reset_email"]:
                flash("That code is incorrect or has expired.")
            else:
                db = get_db()
                db.execute("UPDATE users SET password_hash=? WHERE email=? AND is_admin=0", (generate_password_hash(f["password"]), row["email"]))
                db.commit()
                session.pop("reset_id", None); session.pop("reset_email", None)
                flash("Your password has been updated. Please log in.")
                return redirect(url_for("auth.login"))
    return render_template("reset.html", email=_mask(session["reset_email"]))


@bp.post("/reset/resend")
def reset_resend():
    check_csrf()
    if "reset_email" not in session:
        return redirect(url_for("auth.forgot"))
    try:
        rid = _send_reset(session["reset_email"], session.get("reset_id"))
    except Exception:
        current_app.logger.exception("Could not resend the reset email")
        flash("We couldn't send the email. Please try again.")
        return redirect(url_for("auth.reset"))
    if rid is None:
        flash("Please wait a few seconds before asking for another code.")
    else:
        session["reset_id"] = rid
        flash("If that email is registered, we sent a new code.")
    return redirect(url_for("auth.reset"))


@bp.post("/logout")
def logout():
    check_csrf()
    was_admin = session.get("is_admin")
    session.clear()
    return redirect(url_for("auth.admin_login") if was_admin else url_for("main.home"))
