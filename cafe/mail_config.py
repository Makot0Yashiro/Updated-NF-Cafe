import os

# SMTP account for the OTP emails, from environment variables (see .env.example).
# Gmail: smtp.gmail.com, port 587, TLS, MAIL_USERNAME = your address, MAIL_PASSWORD = an App password.
# If MAIL_USERNAME is empty, codes are printed in the terminal / server log instead of emailed.
MAIL = dict(
    MAIL_SERVER=os.environ.get("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.environ.get("MAIL_PORT", "587")),
    MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "1") == "1",
    MAIL_USE_SSL=os.environ.get("MAIL_USE_SSL", "0") == "1",
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD", ""),
)
MAIL["MAIL_DEFAULT_SENDER"] = ("New Found Cafe", os.environ.get("MAIL_SENDER") or MAIL["MAIL_USERNAME"] or "no-reply@newfoundcafe.local")
