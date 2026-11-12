"""Reading the menu and inventory from the database (categories, menu items with their ingredients, ingredients)."""
from collections import defaultdict
from decimal import Decimal
from urllib.parse import quote
from .db import get_db


def num(v):
    """DECIMAL -> float for JSON / templates (Flask would send Decimal as a string)."""
    return float(v) if isinstance(v, Decimal) else v


def _in(ids):
    return ",".join("?" * len(ids))


# ---------- categories ----------
def category_out(r):
    return {"id": r["id"], "name": r["name"], "group": r["group_name"], "color": r["color"], "emoji": r["emoji"], "sort": r["sort"]}


def categories():
    rows = get_db().execute("SELECT * FROM categories ORDER BY sort, name").fetchall()
    return [category_out(r) for r in rows]


def category(cat_id):
    r = get_db().execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    return category_out(r) if r else None


# ---------- ingredients ----------
def used_in():
    """ingredient id -> [menu item names that use it]"""
    rows = get_db().execute("SELECT r.ingredient_id, m.name FROM menu_item_ingredients r JOIN menu_items m ON m.id=r.item_id ORDER BY m.name").fetchall()
    out = defaultdict(list)
    for r in rows:
        out[r["ingredient_id"]].append(r["name"])
    return out


def ingredient_out(r, used=None):
    d = {"id": r["id"], "name": r["name"], "unit": r["unit"], "stock": num(r["stock"]), "low_at": num(r["low_at"])}
    if used is not None:
        d["used_in"] = used.get(r["id"], [])
    return d


def ingredients(with_usage=True):
    used = used_in() if with_usage else None
    return [ingredient_out(r, used) for r in get_db().execute("SELECT * FROM ingredients ORDER BY name").fetchall()]


def ingredient(ing_id):
    r = get_db().execute("SELECT * FROM ingredients WHERE id=?", (ing_id,)).fetchone()
    return ingredient_out(r, used_in()) if r else None


# ---------- menu items ----------
def _recipes(item_ids):
    """item id -> [{ingredient_id, name, unit, qty, stock}] (qty and stock stay Decimal for exact maths)"""
    out = defaultdict(list)
    if item_ids:
        rows = get_db().execute(
            f"SELECT r.item_id, r.ingredient_id, r.qty, i.name, i.unit, i.stock FROM menu_item_ingredients r "
            f"JOIN ingredients i ON i.id=r.ingredient_id WHERE r.item_id IN ({_in(item_ids)}) ORDER BY i.name", tuple(item_ids)).fetchall()
        for r in rows:
            out[r["item_id"]].append({"ingredient_id": r["ingredient_id"], "name": r["name"], "unit": r["unit"], "qty": r["qty"], "stock": r["stock"]})
    return out


def items(ids=None, active_only=False):
    """Menu items (with recipe) in display order, optionally only the given ids / only active ones."""
    sql, args = ("SELECT m.*, c.name AS cat_name, p.version AS photo_version FROM menu_items m JOIN categories c ON c.id=m.cat_id "
                 "LEFT JOIN menu_item_images p ON p.item_id=m.id"), []
    conds = []
    if ids is not None:
        if not ids:
            return []
        conds.append(f"m.id IN ({_in(ids)})"); args += list(ids)
    if active_only:
        conds.append("m.active=1")
    rows = get_db().execute(sql + (" WHERE " + " AND ".join(conds) if conds else "") + " ORDER BY c.sort, m.sort, m.name", tuple(args)).fetchall()
    recipes = _recipes([r["id"] for r in rows])
    for r in rows:
        r["recipe"] = recipes[r["id"]]
    return rows


def servings(recipe):
    """How many of an item the current stock can make (0 = sold out)."""
    return min((int(r["stock"] // r["qty"]) for r in recipe), default=0)


def photo_url(r):
    """What an item shows: its uploaded photo (versioned URL, cached forever) or else the image URL typed in, or ''."""
    if r.get("photo_version"):
        return f"/media/items/{quote(r['id'])}.webp?v={r['photo_version']}"
    return r["img"] or ""


def item_out(r):
    return {"id": r["id"], "name": r["name"], "cat_id": r["cat_id"], "price": num(r["price"]), "active": bool(r["active"]),
            "img": photo_url(r), "img_url": r["img"] or "", "has_photo": bool(r.get("photo_version")),
            "recipe": [{"ingredient_id": x["ingredient_id"], "name": x["name"], "unit": x["unit"], "qty": num(x["qty"])} for x in r["recipe"]]}


def item(item_id):
    rows = items([item_id])
    return item_out(rows[0]) if rows else None


# ---------- customer menu ----------
def customer_groups():
    """Same shape menu.html has always used: [{name, cats: [{id, name, color, emoji, items: [...]}]}].
    Active items only; categories without active items are left out; sold-out items stay visible but greyed out."""
    by_cat = defaultdict(list)
    for r in items(active_only=True):
        by_cat[r["cat_id"]].append({"id": r["id"], "name": r["name"], "price": num(r["price"]), "img": photo_url(r),
                                    "cat": r["cat_name"], "sold_out": servings(r["recipe"]) < 1})
    groups = {}
    for c in categories():
        if by_cat[c["id"]]:
            groups.setdefault(c["group"], {"name": c["group"], "cats": []})["cats"].append({**c, "items": by_cat[c["id"]]})
    return list(groups.values())
