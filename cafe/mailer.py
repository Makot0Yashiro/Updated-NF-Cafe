"""Email one-time codes (OTP) for sign-up and login, sent over SMTP with Flask-Mail."""
import hmac, hashlib, json, secrets
from datetime import datetime, timedelta, timezone
from flask import current_app
from flask_mail import Mail, Message
from .db import get_db

mail = Mail()
TTL, WAIT, TRIES = 600, 30, 5      # code lifetime (s), seconds between emails, wrong guesses allowed


def _now():
    return datetime.now(timezone.utc)


def _hash(otp_id, code):
    return hmac.new(current_app.secret_key.encode(), f"{otp_id}:{code}".encode(), hashlib.sha256).hexdigest()


def _deliver(email, code, purpose):
    if not current_app.config.get("MAIL_USERNAME"):
        print(f"\n  [SMTP not configured] verification code for {email}: {code}\n")
        return
    action = {"register": "sign up", "login": "log in", "reset": "reset your password"}[purpose]
    msg = Message("Reset your New Found Cafe password" if purpose == "reset" else "Your New Found Cafe verification code", recipients=[email])
    msg.body = (f"Your verification code is {code}. It expires in 10 minutes.\n"
                f"If you didn't try to {action}, you can ignore this email.")
    msg.html = ('<div style="font-family:Arial,sans-serif;max-width:420px;margin:auto;padding:24px;background:#f5efe3;color:#43301f;border-radius:16px">'
                '<h2 style="font-family:Georgia,serif;letter-spacing:.05em;margin:0 0 12px">NEW FOUND CAFE</h2><p>Your verification code is</p>'
                f'<p style="font-size:34px;letter-spacing:8px;font-weight:600;margin:8px 0">{code}</p>'
                '<p style="opacity:.75">It expires in 10 minutes. If this wasn\'t you, you can ignore this email.</p></div>')
    mail.send(msg)


def send_code(email, purpose, payload=None, replace_id=None):
    """Create + email a 6-digit code. Returns the new otp id, or None if asked again too soon."""
    db, now = get_db(), _now()
    db.execute("DELETE FROM email_otps WHERE expires_at < ?", (now.isoformat(),))
    last = db.execute("SELECT created_at FROM email_otps WHERE email=? AND purpose=? ORDER BY id DESC LIMIT 1", (email, purpose)).fetchone()
    if last and (now - datetime.fromisoformat(last["created_at"])).total_seconds() < WAIT:
        return None
    code = f"{secrets.randbelow(10 ** 6):06d}"
    oid = db.execute("INSERT INTO email_otps(email,purpose,code_hash,payload,attempts,expires_at,created_at) VALUES(?,?,?,?,0,?,?)",
                     (email, purpose, "", json.dumps(payload) if payload else None,
                      (now + timedelta(seconds=TTL)).isoformat(), now.isoformat())).lastrowid
    db.execute("UPDATE email_otps SET code_hash=? WHERE id=?", (_hash(oid, code), oid))
    if replace_id:
        db.execute("DELETE FROM email_otps WHERE id=?", (replace_id,))
    db.commit()
    try:
        _deliver(email, code, purpose)
    except Exception:
        db.execute("DELETE FROM email_otps WHERE id=?", (oid,)); db.commit()
        raise
    return oid


def resend_code(otp_id):
    """New id, None (too soon) or False (code no longer exists)."""
    r = get_db().execute("SELECT * FROM email_otps WHERE id=?", (otp_id,)).fetchone()
    if not r:
        return False
    return send_code(r["email"], r["purpose"], json.loads(r["payload"]) if r["payload"] else None, replace_id=otp_id)


def check_code(otp_id, code):
    """Returns (row, None) when the code is right, else (None, message)."""
    db = get_db()
    r = db.execute("SELECT * FROM email_otps WHERE id=?", (otp_id,)).fetchone()
    if not r or r["expires_at"] < _now().isoformat():
        return None, "That code has expired. Please request a new one."
    if r["attempts"] >= TRIES:
        db.execute("DELETE FROM email_otps WHERE id=?", (otp_id,)); db.commit()
        return None, "Too many wrong attempts. Please start again."
    if not hmac.compare_digest(r["code_hash"], _hash(otp_id, code.strip())):
        db.execute("UPDATE email_otps SET attempts=attempts+1 WHERE id=?", (otp_id,)); db.commit()
        return None, "Incorrect code. Please try again."
    db.execute("DELETE FROM email_otps WHERE id=?", (otp_id,)); db.commit()
    return r, None
