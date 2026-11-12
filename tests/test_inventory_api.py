"""Admin JSON API: ingredients, menu items and categories (create / read / update / delete and their errors)."""
import uuid
from conftest import H, ingredients


def uniq(prefix):
    return f"{prefix} {uuid.uuid4().hex[:6]}"


# ---------- ingredients ----------
def test_list_ingredients(admin):
    ings = admin.get("/admin/api/ingredients").get_json()
    tom = next(i for i in ings if i["name"] == "Tomatoes")
    assert set(tom) == {"id", "name", "unit", "stock", "low_at", "used_in"}
    assert tom["used_in"] == ["Burger", "Salad"] and isinstance(tom["stock"], float) and isinstance(tom["low_at"], float)
    assert [i["name"] for i in ings] == sorted(i["name"] for i in ings)


def test_ingredient_create_update_restock_delete(admin):
    name = uniq("Oat milk")
    r = admin.post("/admin/api/ingredients", json={"name": name, "unit": "ml", "stock": 1000, "low_at": 200}, headers=H)
    ing = r.get_json()
    assert r.status_code == 201 and ing["stock"] == 1000.0 and ing["used_in"] == []
    r = admin.put(f"/admin/api/ingredients/{ing['id']}", json={"name": name, "unit": "g", "stock": 900, "low_at": 100}, headers=H)
    assert r.status_code == 200 and r.get_json()["unit"] == "g" and r.get_json()["stock"] == 900.0
    r = admin.post(f"/admin/api/ingredients/{ing['id']}/restock", json={"amount": 150.5}, headers=H)
    assert r.status_code == 200 and r.get_json()["stock"] == 1050.5
    assert admin.delete(f"/admin/api/ingredients/{ing['id']}", headers=H).status_code == 204
    assert name not in ingredients(admin)


def test_ingredient_errors(admin):
    base = {"name": uniq("Thing"), "unit": "g", "stock": 1, "low_at": 0}
    existing = ingredients(admin)["Potatoes"]
    cases = [
        ({**base, "name": "POTATOES"}, 409),            # duplicate name, any case
        ({**base, "unit": "kg"}, 400),
        ({**base, "stock": -1}, 400),
        ({**base, "low_at": "abc"}, 400),
        ({**base, "name": ""}, 400),
    ]
    for body, code in cases:
        r = admin.post("/admin/api/ingredients", json=body, headers=H)
        assert r.status_code == code and r.get_json()["error"], (body, r.get_json())
    assert admin.post("/admin/api/ingredients", json=base).status_code == 400                     # no CSRF header
    r = admin.put(f"/admin/api/ingredients/{existing['id']}", json={**existing, "unit": "pc"}, headers=H)
    assert r.status_code == 409                                                                    # unit of a used ingredient
    r = admin.post(f"/admin/api/ingredients/{existing['id']}/restock", json={"amount": 0}, headers=H)
    assert r.status_code == 400
    r = admin.delete(f"/admin/api/ingredients/{ingredients(admin)['Tomatoes']['id']}", headers=H)
    assert r.status_code == 409 and "Burger" in r.get_json()["error"]
    r = admin.delete("/admin/api/ingredients/999999", headers=H)
    assert r.status_code == 404 and r.is_json


# ---------- menu items ----------
def test_list_menu_items(admin):
    m = admin.get("/admin/api/menu-items").get_json()
    assert set(m) == {"categories", "items", "ingredients"}
    assert {c["id"]: c["group"] for c in m["categories"]} == {"food": "Food", "coffee": "Beverages", "icetea": "Beverages", "floats": "Beverages"}
    fries = next(i for i in m["items"] if i["id"] == "fries")
    assert set(fries) == {"id", "name", "cat_id", "price", "img", "img_url", "has_photo", "active", "recipe"}
    assert set(fries["recipe"][0]) == {"ingredient_id", "name", "unit", "qty"} and fries["price"] == 99.0


def item_body(admin, **over):
    milk = ingredients(admin)["Fresh milk"]["id"]
    return {"name": uniq("Test drink"), "cat_id": "coffee", "price": 99.5, "img": "", "active": True,
            "recipe": [{"ingredient_id": milk, "qty": 100}], **over}


def test_menu_item_create_update_delete(admin):
    ice, syrup = ingredients(admin)["Ice"]["id"], ingredients(admin)["Sugar syrup"]["id"]
    body = item_body(admin, name="Test Item One")
    r = admin.post("/admin/api/menu-items", json=body, headers=H)
    item = r.get_json()
    assert r.status_code == 201 and item["id"] == "test-item-one" and item["price"] == 99.5 and item["recipe"][0]["unit"] == "ml"
    r = admin.post("/admin/api/menu-items", json={**body, "name": "Test-Item-One!"}, headers=H)
    assert r.status_code == 201 and r.get_json()["id"] == "test-item-one-2"                      # slug collision
    r = admin.put("/admin/api/menu-items/test-item-one", headers=H,
                  json={**body, "name": "Renamed One", "recipe": [{"ingredient_id": ice, "qty": 50}, {"ingredient_id": syrup, "qty": 5}]})
    assert r.status_code == 200 and r.get_json()["id"] == "test-item-one" and len(r.get_json()["recipe"]) == 2
    for iid in ("test-item-one", "test-item-one-2"):
        assert admin.delete(f"/admin/api/menu-items/{iid}", headers=H).status_code == 204


def test_menu_item_errors(admin):
    body = item_body(admin)
    milk = body["recipe"][0]
    cases = [
        ({**body, "recipe": []}, 400, "at least one ingredient"),
        ({**body, "recipe": [milk, milk]}, 400, None),
        ({**body, "recipe": [{"ingredient_id": 999999, "qty": 1}]}, 400, None),
        ({**body, "recipe": [{**milk, "qty": 0}]}, 400, None),
        ({**body, "cat_id": "nope"}, 400, None),
        ({**body, "price": 0}, 400, None),
        ({**body, "name": "fries"}, 409, None),                                                  # same name as "Fries"
    ]
    for b, code, words in cases:
        r = admin.post("/admin/api/menu-items", json=b, headers=H)
        assert r.status_code == code, (b, r.get_json())
        assert words is None or words in r.get_json()["error"]
    assert admin.put("/admin/api/menu-items/nope", json=body, headers=H).status_code == 404
    assert admin.delete("/admin/api/menu-items/nope", headers=H).status_code == 404


# ---------- categories ----------
def test_category_create_update_delete(admin):
    name = uniq("Pastries")
    r = admin.post("/admin/api/categories", json={"name": name, "group": "Food", "color": "#AA5500", "emoji": "🥐"}, headers=H)
    cat = r.get_json()
    assert r.status_code == 201 and cat["color"] == "#aa5500" and cat["group"] == "Food" and cat["sort"] >= 5
    r = admin.put(f"/admin/api/categories/{cat['id']}", json={"name": name + " B", "group": "Treats", "color": "#000000", "emoji": "🍰"}, headers=H)
    assert r.status_code == 200 and r.get_json()["group"] == "Treats" and r.get_json()["id"] == cat["id"]
    assert admin.delete(f"/admin/api/categories/{cat['id']}", headers=H).status_code == 204


def test_category_errors(admin):
    good = {"name": uniq("Cat"), "group": "Food", "color": "#123456", "emoji": "🍩"}
    for body, code in [({**good, "name": "COFFEE"}, 409), ({**good, "color": "red"}, 400),
                       ({**good, "emoji": "🍩🍩🍩🍩🍩"}, 400), ({**good, "group": ""}, 400), ({**good, "emoji": ""}, 400)]:
        assert admin.post("/admin/api/categories", json=body, headers=H).status_code == code, body
    r = admin.delete("/admin/api/categories/floats", headers=H)
    assert r.status_code == 409 and r.get_json()["error"].startswith("Move or delete the ") and r.get_json()["error"].endswith(" in Floats first.")
    assert admin.delete("/admin/api/categories/nope", headers=H).status_code == 404
