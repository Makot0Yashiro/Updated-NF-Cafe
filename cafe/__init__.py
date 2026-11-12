import os, secrets
from werkzeug.security import generate_password_hash
from flask import Flask, session
from . import db
from .mailer import mail
from .mail_config import MAIL


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    key_file = os.path.join(app.instance_path, "secret_key")
    if not os.path.exists(key_file):
        with open(key_file, "w") as f:
            f.write(secrets.token_hex(32))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or open(key_file).read().strip(),
    )
    app.config.update(MAIL)
    mail.init_app(app)
    db.init_app(app)
    with app.app_context():                      # make sure an admin account exists
        d = db.get_db()
        if not d.execute("SELECT 1 FROM users WHERE is_admin=1").fetchone():
            email = os.environ.get("ADMIN_EMAIL", "admin@newfoundcafe.com").lower()
            pw = os.environ.get("ADMIN_PASSWORD", "admin123")
            if d.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                d.execute("UPDATE users SET is_admin=1 WHERE email=?", (email,))
            else:
                d.execute("INSERT INTO users(name,email,password_hash,is_admin) VALUES('Admin',?,?,1)",
                          (email, generate_password_hash(pw)))
            d.commit()
            print(f"\n  Admin account created: {email} / {pw}  (set ADMIN_EMAIL / ADMIN_PASSWORD to change)\n")
    from .blueprints import register_blueprints
    register_blueprints(app)

    @app.context_processor
    def inject():
        session.setdefault("csrf", secrets.token_hex(16))
        return {"csrf_token": session["csrf"], "current_user": session.get("user_name"), "is_admin": session.get("is_admin")}

    return app
