import os


MAIL = dict(
    MAIL_SERVER=os.environ.get("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.environ.get("MAIL_PORT", "587")),
    MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "1") == "1",
    MAIL_USE_SSL=os.environ.get("MAIL_USE_SSL", "0") == "1",
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME", "gadbrionesss@gmail.com"), # <- your Gmail address
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD", "qobasavnskhfubwu"), # <- your Gmail App password
)
MAIL["MAIL_DEFAULT_SENDER"] = ("New Found Cafe", os.environ.get("MAIL_SENDER") or MAIL["MAIL_USERNAME"] or "no-reply@newfoundcafe.local")
