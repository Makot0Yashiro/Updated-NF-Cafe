from flask import Blueprint, render_template

bp = Blueprint("main", __name__)

CDN = "https://cdn.prod.website-files.com/67bcaa3190819435d319a786/"

# Carousel photos on the landing page.
# "src" is either a full https:// URL or a file name inside cafe/static/images/
# (e.g. "latte.jpg"). Add, remove or reorder entries freely - 4 or more looks best.
GALLERY = [
    {"src": CDN + "67bcaa3190819435d319a7ab_5b949447b3128c62d2f78db825e3a7a1_img_1.avif", "alt": "Inside New Found Cafe"},
    {"src": CDN + "67bcaa3190819435d319a7b6_ddf378cd0b77da633bb6029bc60e671c_img_2.avif", "alt": "Our cafe interior"},
    {"src": CDN + "67bcaa3190819435d319a7ad_82fb3915470160aabb14d005afd9f98c_img_3.avif", "alt": "Coffee and pastries"},
    {"src": CDN + "67bcaa3190819435d319a7ac_c79e17c6934830315efcef3f223e9e15_img_4.avif", "alt": "A corner of the cafe"},
]


@bp.get("/")
def home():
    return render_template("home.html", gallery=GALLERY)
