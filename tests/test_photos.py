"""Menu item photo upload / replace / remove, how photos are served, and the image processing rules."""
import io
from PIL import Image
from conftest import H, ingredients, q


def image_bytes(fmt, size=(1600, 1200), mode="RGB", exif=None):
    b = io.BytesIO()
    kwargs = {"exif": exif} if exif else {}
    Image.new(mode, size, (200, 80, 40, 255) if mode == "RGBA" else (200, 80, 40)).save(b, fmt, **kwargs)
    return b.getvalue()


def upload(admin, item_id, data, filename="photo.jpg"):
    return admin.post(f"/admin/api/menu-items/{item_id}/image", data={"file": (io.BytesIO(data), filename)},
                      headers=H, content_type="multipart/form-data")


def new_item(admin, name):
    milk = ingredients(admin)["Fresh milk"]["id"]
    r = admin.post("/admin/api/menu-items", headers=H, json={"name": name, "cat_id": "coffee", "price": 100, "img": "https://example.com/x.jpg",
                                                               "active": True, "recipe": [{"ingredient_id": milk, "qty": 100}]})
    assert r.status_code == 201
    return r.get_json()["id"]


def test_upload_each_format_and_serve(admin, customer):
    iid = new_item(admin, "Photo Test A")
    gps = Image.Exif(); gps[0x0112] = 6; gps[0x010F] = "PhoneCam"
    for fmt, mode, exif in [("JPEG", "RGB", gps.tobytes()), ("PNG", "RGBA", None), ("WEBP", "RGB", None)]:
        r = upload(admin, iid, image_bytes(fmt, mode=mode, exif=exif), f"p.{fmt.lower()}")
        item = r.get_json()
        assert r.status_code == 200 and item["has_photo"] and item["img"].startswith(f"/media/items/{iid}.webp?v=")
        assert item["img_url"] == "https://example.com/x.jpg"                    # the typed URL is kept, just not shown
        served = customer.get(item["img"])
        assert served.status_code == 200 and served.mimetype == "image/webp"
        assert served.headers["Cache-Control"] == "public, max-age=31536000, immutable"
        img = Image.open(io.BytesIO(served.data))
        assert max(img.size) <= 1000 and not img.getexif()                        # resized, metadata stripped
        if exif:
            assert img.size == (750, 1000)                                        # rotated by the EXIF orientation
    assert item["img"] in customer.get("/menu").get_data(as_text=True)
    assert customer.get(f"/media/items/{iid}.webp?v=old").headers["Cache-Control"] == "public, no-cache"


def test_replace_remove_and_delete_item(admin):
    iid = new_item(admin, "Photo Test B")
    v1 = upload(admin, iid, image_bytes("PNG")).get_json()["img"]
    v2 = upload(admin, iid, image_bytes("PNG", size=(800, 800))).get_json()["img"]
    assert v1 != v2                                                               # new photo -> new ?v=
    r = admin.delete(f"/admin/api/menu-items/{iid}/image", headers=H)
    assert r.status_code == 200 and not r.get_json()["has_photo"] and r.get_json()["img"] == "https://example.com/x.jpg"
    assert admin.get(f"/media/items/{iid}.webp").status_code == 404
    upload(admin, iid, image_bytes("PNG"))
    assert admin.delete(f"/admin/api/menu-items/{iid}", headers=H).status_code == 204
    assert not q("SELECT 1 FROM menu_item_images WHERE item_id=%s", (iid,))       # photo deleted with the item


def test_upload_refused(admin):
    iid = new_item(admin, "Photo Test C")
    r = upload(admin, iid, b"hello, I am not an image", "fake.jpg")
    assert r.status_code == 400 and r.get_json()["error"] == "That file isn't a JPEG, PNG or WebP image."
    gif = io.BytesIO(); Image.new("RGB", (10, 10)).save(gif, "GIF")
    assert upload(admin, iid, gif.getvalue(), "a.gif").status_code == 400
    r = upload(admin, iid, b"\xff" * (6 * 1024 * 1024), "big.jpg")
    assert r.status_code == 413 and r.get_json()["error"] == "Photo is too large, max 5 MB."
    r = admin.post(f"/admin/api/menu-items/{iid}/image", data={}, headers=H, content_type="multipart/form-data")
    assert r.status_code == 400
    assert upload(admin, "nope", image_bytes("PNG")).status_code == 404
    admin.delete(f"/admin/api/menu-items/{iid}", headers=H)
