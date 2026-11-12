"""Admin inventory pages: ingredients and menu items.
Page routes only for now. The pages fetch their data from /admin/api/ingredients and /admin/api/menu-items (to be added)."""
from flask import Blueprint, render_template
from .admin import admin_required

bp = Blueprint("inventory", __name__)


@bp.get("/admin/inventory")
@admin_required
def ingredients_page():
    return render_template("admin_inventory.html", page="inventory")


@bp.get("/admin/menu-items")
@admin_required
def items_page():
    return render_template("admin_menu_items.html", page="items")
