from flask import Blueprint, render_template, session
from ..auth_utils import login_required
from ..menu_data import COUPONS
from ..catalog import customer_groups
from .account import profile

bp = Blueprint("menu", __name__)


@bp.get("/menu")
@login_required
def menu():
    return render_template("menu.html", groups=customer_groups(), coupons=COUPONS, me=profile(session["user_id"]))
