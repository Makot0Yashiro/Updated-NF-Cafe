from decimal import Decimal

import pytest

from cafe.models import Admin, Customer, Ingredient, MenuItem, Order, RecipeIngredient, User


def test_customer_and_admin_models_share_password_behavior():
    password_hash = User.hash_password("secure-pass")
    customer = Customer(1, "Cafe Guest", "guest@test.local", password_hash)
    admin = Admin(2, "Cafe Admin", "admin@test.local", password_hash)

    assert customer.verify_password("secure-pass")
    assert not customer.is_admin
    assert admin.verify_password("secure-pass")
    assert admin.is_admin


def test_ingredient_stock_methods_validate_and_restock():
    ingredient = Ingredient(1, "Coffee", "g", Decimal("10"), Decimal("2"))
    ingredient.restock("2.5")
    assert ingredient.stock == Decimal("12.5")

    with pytest.raises(ValueError):
        ingredient.set_stock(-1)
    with pytest.raises(ValueError):
        ingredient.restock(0)


def test_menu_item_calculates_servings_from_recipe_stock():
    recipe = [RecipeIngredient(1, "Beans", "g", Decimal("2"), Decimal("11")),
              RecipeIngredient(2, "Milk", "ml", Decimal("3"), Decimal("12"))]
    item = MenuItem("latte", "Latte", "drinks", "Drinks", Decimal("5.5"), True, "", 1, recipe)

    assert item.servings() == 4
    assert item.to_customer_dict()["sold_out"] is False


def test_order_rejects_status_and_payment_values_outside_their_lifecycle():
    order = Order(1, "pickup", "Received", "unpaid")
    order.set_status("Completed")
    order.set_payment_status("paid")
    assert order.status == "Completed" and order.pay_status == "paid"

    with pytest.raises(ValueError):
        order.set_status("Out for delivery")
    with pytest.raises(ValueError):
        order.set_payment_status("unpaid")
