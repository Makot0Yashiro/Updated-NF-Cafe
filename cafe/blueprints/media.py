"""Public media: menu item photos stored in the database (shown on the customer menu, so no login)."""
from flask import Blueprint, Response, abort, request
from ..db import get_db
from ..repositories import MenuRepository

bp = Blueprint("media", __name__)


@bp.get("/media/items/<item_id>.webp")
def item_photo(item_id):
    r = MenuRepository(get_db()).image(item_id) or abort(404)
    resp = Response(bytes(r["data"]), mimetype=r["mime"])
    resp.set_etag(r["version"])
    if request.args.get("v") == r["version"]:      # versioned URL: the bytes behind it never change
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        resp.headers["Cache-Control"] = "public, no-cache"
    return resp.make_conditional(request)
