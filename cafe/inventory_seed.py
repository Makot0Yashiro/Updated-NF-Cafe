"""Starter menu + inventory, inserted once by db._upgrade() when the categories table is empty.
After that, everything is managed in Admin > Inventory and Admin > Menu items."""


def _img(keywords, n):
    # Placeholder stock photos (loremflickr = random Flickr photo for the keywords). Replace in Admin > Menu items.
    return f"https://loremflickr.com/480/360/{keywords}?lock={n}"


# id, name, group, color, emoji
CATEGORIES = [
    ("food", "Food", "Food", "#c8553d", "🍔"),
    ("coffee", "Coffee", "Beverages", "#8a5a33", "☕"),
    ("icetea", "Ice Tea", "Beverages", "#3f8a6b", "🧋"),
    ("floats", "Floats", "Beverages", "#b5578a", "🍨"),
]

# name, unit, stock, low_at
INGREDIENTS = [
    ("Potatoes", "g", 8000, 2000), ("Cooking oil", "ml", 5000, 1000), ("Salt", "g", 1000, 200),
    ("Tortilla chips", "g", 3000, 800), ("Cheese sauce", "ml", 400, 500), ("Burger buns", "pc", 24, 10),
    ("Beef patties", "pc", 6, 10), ("Lettuce", "g", 1500, 300), ("Tomatoes", "g", 0, 300),
    ("Salad dressing", "ml", 1200, 300), ("Espresso beans", "g", 2500, 500), ("Fresh milk", "ml", 9000, 2000),
    ("Matcha powder", "g", 600, 150), ("Caramel syrup", "ml", 800, 200), ("Chocolate syrup", "ml", 1500, 300),
    ("Cream cookies", "pc", 40, 20), ("Cherry syrup", "ml", 700, 200), ("Vanilla ice cream", "g", 4000, 1000),
    ("Black tea", "g", 900, 200), ("Ice", "g", 20000, 5000), ("Sugar syrup", "ml", 2000, 500),
    ("Paper straws", "pc", 300, 100),
]

# category id -> [(item id, name, price, image keywords, {ingredient name: qty per serving})]
ITEMS = {
    "food": [
        ("fries", "Fries", 99, "french,fries", {"Potatoes": 200, "Cooking oil": 30, "Salt": 2}),
        ("nachos", "Nachos", 149, "nachos", {"Tortilla chips": 150, "Cheese sauce": 60}),
        ("burger", "Burger", 189, "burger", {"Burger buns": 1, "Beef patties": 1, "Lettuce": 20, "Tomatoes": 30}),
        ("salad", "Salad", 139, "salad", {"Lettuce": 120, "Tomatoes": 60, "Salad dressing": 30})],
    "coffee": [
        ("c-matcha", "Matcha Latte", 135, "matcha,latte", {"Matcha powder": 5, "Fresh milk": 200, "Sugar syrup": 15}),
        ("c-latte", "Coffee Latte", 120, "latte,coffee", {"Espresso beans": 18, "Fresh milk": 200}),
        ("c-caramel", "Salted Caramel", 140, "caramel,coffee", {"Espresso beans": 18, "Fresh milk": 180, "Caramel syrup": 30, "Salt": 1}),
        ("c-americano", "Americano", 95, "americano,coffee", {"Espresso beans": 18})],
    "icetea": [
        ("t-matcha", "Matcha Iced Tea", 130, "iced,matcha", {"Matcha powder": 5, "Ice": 150, "Sugar syrup": 20, "Fresh milk": 100, "Paper straws": 1}),
        ("t-oreo", "Cookies and Cream", 140, "oreo,milkshake", {"Cream cookies": 3, "Fresh milk": 200, "Ice": 150, "Paper straws": 1}),
        ("t-blackforest", "Black Forest Iced Tea", 145, "chocolate,cherry,drink", {"Black tea": 4, "Chocolate syrup": 20, "Cherry syrup": 20, "Ice": 150, "Paper straws": 1}),
        ("t-choco", "Chocolate Iced Tea", 130, "iced,chocolate,drink", {"Black tea": 4, "Chocolate syrup": 30, "Ice": 150, "Paper straws": 1})],
    "floats": [
        ("f-choco", "Chocolate Float", 150, "chocolate,float", {"Chocolate syrup": 30, "Fresh milk": 150, "Vanilla ice cream": 80, "Paper straws": 1}),
        ("f-blackforest", "Black Forest Float", 160, "icecream,float,cherry", {"Chocolate syrup": 20, "Cherry syrup": 20, "Vanilla ice cream": 80, "Fresh milk": 150, "Paper straws": 1}),
        ("f-matcha", "Matcha Float", 155, "matcha,icecream", {"Matcha powder": 5, "Fresh milk": 150, "Vanilla ice cream": 80, "Paper straws": 1})],
}


def seed(cur):
    """Insert the starter data with a plain mysql-connector cursor. Caller commits."""
    for n, (cid, name, group, color, emoji) in enumerate(CATEGORIES, start=1):
        cur.execute("INSERT INTO categories(id,name,group_name,color,emoji,sort) VALUES(%s,%s,%s,%s,%s,%s)", (cid, name, group, color, emoji, n))
    ing_id = {}
    for name, unit, stock, low_at in INGREDIENTS:
        cur.execute("INSERT INTO ingredients(name,unit,stock,low_at) VALUES(%s,%s,%s,%s)", (name, unit, stock, low_at))
        ing_id[name] = cur.lastrowid
    sort = 0
    for cid, rows in ITEMS.items():
        for k, (iid, name, price, kw, recipe) in enumerate(rows, start=len(cid) * 7):   # same photo "lock" numbers as the old menu_data.py
            sort += 1
            cur.execute("INSERT INTO menu_items(id,name,cat_id,price,img,active,sort) VALUES(%s,%s,%s,%s,%s,1,%s)",
                        (iid, name, cid, price, _img(kw, k), sort))
            for ing, qty in recipe.items():
                cur.execute("INSERT INTO menu_item_ingredients(item_id,ingredient_id,qty) VALUES(%s,%s,%s)", (iid, ing_id[ing], qty))
