import os, secrets
try:                                             # local convenience: read settings from a .env file (see .env.example)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from flask import Flask, session, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from . import db
from .config import PRODUCTION
from .images import MAX_UPLOAD_BYTES
from .mailer import mail
from .mail_config import MAIL


def _secret_key(app):
    key = os.environ.get("SECRET_KEY", "").strip()
    if key:
        return key
    if PRODUCTION:
        raise SystemExit("\nSECRET_KEY is not set. Set it to a long random value (Render can generate one), then start again.\n")
    os.makedirs(app.instance_path, exist_ok=True)     # local only: keep a random key in instance/ (git-ignored)
    key_file = os.path.join(app.instance_path, "secret_key")
    if not os.path.exists(key_file):
        with open(key_file, "w") as f:
            f.write(secrets.token_hex(32))
    with open(key_file) as f:
        return f.read().strip()


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(SECRET_KEY=_secret_key(app), MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES + 256 * 1024)   # room for the form around a 5 MB photo
    if PRODUCTION:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)   # Render terminates HTTPS in front of the app
        app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", PREFERRED_URL_SCHEME="https")
        if not MAIL["MAIL_USERNAME"]:
            print("\n  WARNING: MAIL_USERNAME is not set, so verification codes only appear in the server log.\n")
    app.config.update(MAIL)
    mail.init_app(app)
    db.init_app(app)                              # creates / upgrades / seeds the database and the first admin
    from .blueprints import register_blueprints
    register_blueprints(app)

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.errorhandler(413)
    def too_large(e):
        if request.path.startswith("/admin/api/"):
            return jsonify(error="Photo is too large, max 5 MB."), 413
        return e

    @app.context_processor
    def inject():
        session.setdefault("csrf", secrets.token_hex(16))
        return {"csrf_token": session["csrf"], "current_user": session.get("user_name"), "is_admin": session.get("is_admin")}

    return app
