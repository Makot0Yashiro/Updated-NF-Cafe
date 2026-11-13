"""Compatibility helpers for the menu, category, and ingredient repositories."""
from collections import defaultdict
from decimal import Decimal

from .db import get_db
from .repositories import MenuRepository


def _repository():
    return MenuRepository(get_db())


def num(value):
    """DECIMAL -> float for JSON / templates (Flask would send Decimal as a string)."""
    return float(value) if isinstance(value, Decimal) else value


def category_out(category):
    return category.to_dict()


def categories():
    return [category_out(category) for category in _repository().categories()]


def category(cat_id):
    result = _repository().category(cat_id)
    return category_out(result) if result else None


def used_in():
    """Ingredient id -> menu item names that use it."""
    return _repository().used_in()


def ingredient_out(ingredient, used=None):
    return ingredient.to_dict(include_usage=used is not None)


def ingredients(with_usage=True):
    return [ingredient_out(ingredient, {} if with_usage else None)
            for ingredient in _repository().ingredients(with_usage)]


def ingredient(ing_id):
    result = _repository().ingredient(ing_id)
    return ingredient_out(result, {}) if result else None


def items(ids=None, active_only=False):
    """Return repository menu entities as records for existing route/service callers."""
    filters = {"active_only": active_only}
    if ids is not None:
        filters["ids"] = ids
    return [item.to_record() for item in _repository().list(**filters)]


def servings(recipe):
    """How many of an item the current stock can make (0 = sold out)."""
    return min((int(row["stock"] // row["qty"]) for row in recipe), default=0)


def photo_url(row):
    """What an item shows: its uploaded photo or else the image URL typed in."""
    if row.get("photo_version"):
        from urllib.parse import quote
        return f"/media/items/{quote(row['id'])}.webp?v={row['photo_version']}"
    return row.get("img") or ""


def item_out(row):
    return {"id": row["id"], "name": row["name"], "cat_id": row["cat_id"], "price": num(row["price"]), "active": bool(row["active"]),
            "img": photo_url(row), "img_url": row["img"] or "", "has_photo": bool(row.get("photo_version")),
            "recipe": [{"ingredient_id": part["ingredient_id"], "name": part["name"], "unit": part["unit"], "qty": num(part["qty"])}
                       for part in row["recipe"]]}


def item(item_id):
    rows = items([item_id])
    return item_out(rows[0]) if rows else None


def customer_groups():
    """Keep the existing menu.html structure and show active and sold-out items."""
    by_cat = defaultdict(list)
    for row in items(active_only=True):
        by_cat[row["cat_id"]].append({"id": row["id"], "name": row["name"], "price": num(row["price"]),
                                      "img": photo_url(row), "cat": row["cat_name"],
                                      "sold_out": servings(row["recipe"]) < 1})
    groups = {}
    for category_data in categories():
        if by_cat[category_data["id"]]:
            groups.setdefault(category_data["group"], {"name": category_data["group"], "cats": []})["cats"].append(
                {**category_data, "items": by_cat[category_data["id"]]})
    return list(groups.values())
