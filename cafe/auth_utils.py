import re
import secrets
from functools import wraps
from flask import session, request, redirect, url_for, abort, jsonify

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        if session.get("is_admin"):              # admins only get order management + analytics, no ordering
            if request.path.startswith("/api/"):
                return jsonify(error="Admins cannot place orders"), 403
            return redirect(url_for("admin.dashboard"))
        return f(*a, **kw)
    return wrapper


def valid_email(value):
    return isinstance(value, str) and _EMAIL_RE.fullmatch(value) is not None


def check_csrf():
    t = request.headers.get("X-CSRFToken") or request.form.get("csrf") or ""
    if not secrets.compare_digest(t, session.get("csrf", "")):
        abort(400, "Bad CSRF token")
