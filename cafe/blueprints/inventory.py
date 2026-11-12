"""Admin inventory: the Inventory / Menu items pages and their JSON API (ingredients, menu items, categories).
Every error is {"error": "..."} with a 4xx status; the pages show that text as-is."""
import re
from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, request, jsonify
from ..db import get_db, IntegrityError
from ..auth_utils import check_csrf
from .. import catalog, images
from .admin import admin_required

bp = Blueprint("inventory", __name__)
UNITS = ("g", "ml", "pc")
MAX_AMOUNT = Decimal("999999999")


class Invalid(Exception):
    """Raised by validators; becomes {"error": message} with the given status."""
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@bp.errorhandler(Invalid)
def _invalid(e):
    get_db().rollback()
    return jsonify(error=str(e)), e.status


def _body():
    check_csrf()
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise Invalid("Send the details as JSON.")
    return d


def _text(d, key, label, max_len, required=True):
    v = str(d.get(key) or "").strip()
    if required and not v:
        raise Invalid(f"{label} is required.")
    if len(v) > max_len:
        raise Invalid(f"{label} can be at most {max_len} characters.")
    return v


def _amount(v, label, positive=False):
    try:
        n = Decimal(str(v))
        assert n.is_finite()
    except (InvalidOperation, AssertionError, ValueError):
        raise Invalid(f"{label} must be a number.")
    if n < 0 or (positive and n == 0):
        raise Invalid(f"{label} must be {'greater than 0' if positive else '0 or more'}.")
    if n > MAX_AMOUNT:
        raise Invalid(f"{label} is too large.")
    return n.quantize(Decimal("0.001"))


def _unique(table, name, own_id=None, label="name"):
    if get_db().execute(f"SELECT 1 FROM {table} WHERE LOWER(name)=LOWER(?) AND id<>?", (name, own_id if own_id is not None else "")).fetchone():
        raise Invalid(f"Something with the {label} “{name}” already exists.", 409)


def _slug(table, name):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:34] or {"menu_items": "item", "categories": "category"}[table]
    slug, n = base, 2
    while get_db().execute(f"SELECT 1 FROM {table} WHERE id=?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _next_sort(table):
    return (get_db().execute(f"SELECT COALESCE(MAX(sort), 0) AS s FROM {table}").fetchone()["s"]) + 1


def _commit(make_response):
    """Commit, turning a duplicate-key race into a friendly 409."""
    try:
        get_db().commit()
    except IntegrityError:
        raise Invalid("That name is already taken.", 409)
    return make_response()


# ===================== pages =====================
@bp.get("/admin/inventory")
@admin_required
def ingredients_page():
    return render_template("admin_inventory.html", page="inventory")


@bp.get("/admin/menu-items")
@admin_required
def items_page():
    return render_template("admin_menu_items.html", page="items")


# ===================== ingredients =====================
def _ingredient_or_404(ing_id, lock=False):
    r = get_db().execute("SELECT * FROM ingredients WHERE id=?" + (" FOR UPDATE" if lock else ""), (ing_id,)).fetchone()
    if not r:
        raise Invalid("That ingredient no longer exists. Reload the page.", 404)
    return r


def _ingredient_fields(d, own_id=None):
    name = _text(d, "name", "Name", 80)
    unit = d.get("unit")
    if unit not in UNITS:
        raise Invalid("Unit must be g, ml or pc.")
    stock, low_at = _amount(d.get("stock"), "In stock"), _amount(d.get("low_at"), "Low-stock alert")
    _unique("ingredients", name, own_id, "ingredient name")
    return name, unit, stock, low_at


@bp.get("/admin/api/ingredients")
@admin_required
def list_ingredients():
    return jsonify(catalog.ingredients())


@bp.post("/admin/api/ingredients")
@admin_required
def add_ingredient():
    name, unit, stock, low_at = _ingredient_fields(_body())
    cur = get_db().execute("INSERT INTO ingredients(name,unit,stock,low_at) VALUES(?,?,?,?)", (name, unit, stock, low_at))
    return _commit(lambda: (jsonify(catalog.ingredient(cur.lastrowid)), 201))


@bp.put("/admin/api/ingredients/<int:ing_id>")
@admin_required
def edit_ingredient(ing_id):
    d = _body()
    old = _ingredient_or_404(ing_id, lock=True)
    name, unit, stock, low_at = _ingredient_fields(d, ing_id)
    used = catalog.used_in().get(ing_id, [])
    if unit != old["unit"] and used:
        raise Invalid(f"Can't change the unit while {', '.join(used)} use it. Remove it from those items first.", 409)
    get_db().execute("UPDATE ingredients SET name=?, unit=?, stock=?, low_at=? WHERE id=?", (name, unit, stock, low_at, ing_id))
    return _commit(lambda: jsonify(catalog.ingredient(ing_id)))


@bp.post("/admin/api/ingredients/<int:ing_id>/restock")
@admin_required
def restock_ingredient(ing_id):
    amount = _amount(_body().get("amount"), "Amount", positive=True)
    row = _ingredient_or_404(ing_id, lock=True)
    if row["stock"] + amount > MAX_AMOUNT:
        raise Invalid("That would make the stock too large.")
    get_db().execute("UPDATE ingredients SET stock = stock + ? WHERE id=?", (amount, ing_id))
    return _commit(lambda: jsonify(catalog.ingredient(ing_id)))


@bp.delete("/admin/api/ingredients/<int:ing_id>")
@admin_required
def delete_ingredient(ing_id):
    check_csrf()
    _ingredient_or_404(ing_id, lock=True)
    used = catalog.used_in().get(ing_id, [])
    if used:
        raise Invalid(f"Used in {', '.join(used)}. Remove it from those items first.", 409)
    get_db().execute("DELETE FROM ingredients WHERE id=?", (ing_id,))
    return _commit(lambda: ("", 204))


# ===================== menu items =====================
def _item_or_404(item_id):
    if not get_db().execute("SELECT 1 FROM menu_items WHERE id=? FOR UPDATE", (item_id,)).fetchone():
        raise Invalid("That menu item no longer exists. Reload the page.", 404)


def _item_fields(d, own_id=None):
    name = _text(d, "name", "Name", 80)
    cat_id = str(d.get("cat_id") or "")
    if not catalog.category(cat_id):
        raise Invalid("Choose a category.")
    price = _amount(d.get("price"), "Price", positive=True)
    if price > 100000:
        raise Invalid("Price is too large.")
    img = _text(d, "img", "Image URL", 300, required=False)
    recipe = d.get("recipe")
    if not isinstance(recipe, list) or not recipe:
        raise Invalid("Add at least one ingredient. Every menu item needs one so its stock can be tracked.")
    rows, seen = [], set()
    for r in recipe:
        try:
            ing_id = int(r.get("ingredient_id"))
        except (TypeError, ValueError, AttributeError):
            raise Invalid("Choose an ingredient in every row.")
        if ing_id in seen:
            raise Invalid("Each ingredient can only be listed once.")
        seen.add(ing_id)
        rows.append((ing_id, _amount(r.get("qty"), "Every ingredient amount", positive=True)))
    found = {r["id"] for r in get_db().execute(f"SELECT id FROM ingredients WHERE id IN ({','.join('?' * len(seen))})", tuple(seen)).fetchall()}
    if found != seen:
        raise Invalid("One of the ingredients no longer exists. Reload the page.")
    _unique("menu_items", name, own_id, "menu item name")
    return name, cat_id, price, img, bool(d.get("active", True)), rows


def _save_recipe(item_id, rows):
    db = get_db()
    db.execute("DELETE FROM menu_item_ingredients WHERE item_id=?", (item_id,))
    for ing_id, qty in rows:
        db.execute("INSERT INTO menu_item_ingredients(item_id,ingredient_id,qty) VALUES(?,?,?)", (item_id, ing_id, qty))


@bp.get("/admin/api/menu-items")
@admin_required
def list_items():
    return jsonify(categories=catalog.categories(), items=[catalog.item_out(r) for r in catalog.items()],
                   ingredients=catalog.ingredients(with_usage=False))


@bp.post("/admin/api/menu-items")
@admin_required
def add_item():
    name, cat_id, price, img, active, rows = _item_fields(_body())
    item_id = _slug("menu_items", name)
    get_db().execute("INSERT INTO menu_items(id,name,cat_id,price,img,active,sort) VALUES(?,?,?,?,?,?,?)",
                     (item_id, name, cat_id, price, img, int(active), _next_sort("menu_items")))
    _save_recipe(item_id, rows)
    return _commit(lambda: (jsonify(catalog.item(item_id)), 201))


@bp.put("/admin/api/menu-items/<item_id>")
@admin_required
def edit_item(item_id):
    d = _body()
    _item_or_404(item_id)
    name, cat_id, price, img, active, rows = _item_fields(d, item_id)
    get_db().execute("UPDATE menu_items SET name=?, cat_id=?, price=?, img=?, active=? WHERE id=?", (name, cat_id, price, img, int(active), item_id))
    _save_recipe(item_id, rows)
    return _commit(lambda: jsonify(catalog.item(item_id)))


@bp.delete("/admin/api/menu-items/<item_id>")
@admin_required
def delete_item(item_id):
    check_csrf()
    _item_or_404(item_id)
    get_db().execute("DELETE FROM menu_items WHERE id=?", (item_id,))   # recipe rows + photo go with it (ON DELETE CASCADE)
    return _commit(lambda: ("", 204))


@bp.post("/admin/api/menu-items/<item_id>/image")
@admin_required
def upload_item_image(item_id):
    check_csrf()
    _item_or_404(item_id)
    f = request.files.get("file")
    if not f:
        raise Invalid("Choose a photo to upload.")
    try:
        data, mime, version = images.process(f.read(images.MAX_UPLOAD_BYTES + 1))
    except images.BadImage as e:
        raise Invalid(str(e), e.status)
    get_db().execute("INSERT INTO menu_item_images(item_id,mime,data,version,updated_at) VALUES(?,?,?,?,UTC_TIMESTAMP()) "
                     "ON DUPLICATE KEY UPDATE mime=VALUES(mime), data=VALUES(data), version=VALUES(version), updated_at=VALUES(updated_at)",
                     (item_id, mime, data, version))
    return _commit(lambda: jsonify(catalog.item(item_id)))


@bp.delete("/admin/api/menu-items/<item_id>/image")
@admin_required
def delete_item_image(item_id):
    check_csrf()
    _item_or_404(item_id)
    get_db().execute("DELETE FROM menu_item_images WHERE item_id=?", (item_id,))
    return _commit(lambda: jsonify(catalog.item(item_id)))


# ===================== categories =====================
def _category_or_404(cat_id):
    if not get_db().execute("SELECT 1 FROM categories WHERE id=? FOR UPDATE", (cat_id,)).fetchone():
        raise Invalid("That category no longer exists. Reload the page.", 404)


def _category_fields(d, own_id=None):
    name = _text(d, "name", "Name", 60)
    group = _text(d, "group", "Group", 60)
    color = str(d.get("color") or "")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise Invalid("Colour must look like #8a5a33.")
    emoji = _text(d, "emoji", "Emoji", 4)          # len() counts characters (code points), not bytes
    _unique("categories", name, own_id, "category name")
    return name, group, color.lower(), emoji


@bp.post("/admin/api/categories")
@admin_required
def add_category():
    name, group, color, emoji = _category_fields(_body())
    cat_id = _slug("categories", name)
    get_db().execute("INSERT INTO categories(id,name,group_name,color,emoji,sort) VALUES(?,?,?,?,?,?)",
                     (cat_id, name, group, color, emoji, _next_sort("categories")))
    return _commit(lambda: (jsonify(catalog.category(cat_id)), 201))


@bp.put("/admin/api/categories/<cat_id>")
@admin_required
def edit_category(cat_id):
    d = _body()
    _category_or_404(cat_id)
    name, group, color, emoji = _category_fields(d, cat_id)
    get_db().execute("UPDATE categories SET name=?, group_name=?, color=?, emoji=? WHERE id=?", (name, group, color, emoji, cat_id))
    return _commit(lambda: jsonify(catalog.category(cat_id)))


@bp.delete("/admin/api/categories/<cat_id>")
@admin_required
def delete_category(cat_id):
    check_csrf()
    _category_or_404(cat_id)
    n = get_db().execute("SELECT COUNT(*) AS n FROM menu_items WHERE cat_id=?", (cat_id,)).fetchone()["n"]
    if n:
        name = catalog.category(cat_id)["name"]
        raise Invalid(f"Move or delete the {n} item{'s' if n != 1 else ''} in {name} first.", 409)
    get_db().execute("DELETE FROM categories WHERE id=?", (cat_id,))
    return _commit(lambda: ("", 204))
