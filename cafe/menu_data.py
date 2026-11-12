# Edit menu items, prices, images, coupons and the cafe location here.
CAFE_LOCATION = (14.2781, 121.4161)   # Santa Cruz, Laguna (lat, lng)


def _img(keywords, n):
    # Placeholder stock photos (loremflickr = random Flickr photo for the keywords).
    # To use your own photos: put files in cafe/static/images/ and set "img" to "/static/images/<file>".
    return f"https://loremflickr.com/480/360/{keywords}?lock={n}"


def _cat(cid, name, color, emoji, rows):
    return {"id": cid, "name": name, "color": color, "emoji": emoji,
            "items": [{"id": r[0], "name": r[1], "price": r[2], "img": _img(r[3], k), "cat": name}
                      for k, r in enumerate(rows, start=len(cid) * 7)]}


# id, display name, price, image keywords
GROUPS = [
    {"name": "Food", "cats": [
        _cat("food", "Food", "#c8553d", "🍔", [
            ("fries", "Fries", 99, "french,fries"),
            ("nachos", "Nachos", 149, "nachos"),
            ("burger", "Burger", 189, "burger"),
            ("salad", "Salad", 139, "salad")])]},
    {"name": "Beverages", "cats": [
        _cat("coffee", "Coffee", "#8a5a33", "☕", [
            ("c-matcha", "Matcha Latte", 135, "matcha,latte"),
            ("c-latte", "Coffee Latte", 120, "latte,coffee"),
            ("c-caramel", "Salted Caramel", 140, "caramel,coffee"),
            ("c-americano", "Americano", 95, "americano,coffee")]),
        _cat("icetea", "Ice Tea", "#3f8a6b", "🧋", [
            ("t-matcha", "Matcha Iced Tea", 130, "iced,matcha"),
            ("t-oreo", "Cookies and Cream", 140, "oreo,milkshake"),
            ("t-blackforest", "Black Forest Iced Tea", 145, "chocolate,cherry,drink"),
            ("t-choco", "Chocolate Iced Tea", 130, "iced,chocolate,drink")]),
        _cat("floats", "Floats", "#b5578a", "🍨", [
            ("f-choco", "Chocolate Float", 150, "chocolate,float"),
            ("f-blackforest", "Black Forest Float", 160, "icecream,float,cherry"),
            ("f-matcha", "Matcha Float", 155, "matcha,icecream")])]},
]
CATS = [c for g in GROUPS for c in g["cats"]]
ITEMS = {i["id"]: i for c in CATS for i in c["items"]}
COUPONS = {"WELCOME10": 0.10}   # code -> discount rate
