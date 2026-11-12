"""Menu item photos: check an upload really is an image, fix its rotation, strip metadata, shrink it and save it as WebP."""
import hashlib, io, warnings
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SIDE = 1000
FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 40_000_000                # refuse "decompression bomb" images

TOO_LARGE = "Photo is too large, max 5 MB."
NOT_IMAGE = "That file isn't a JPEG, PNG or WebP image."


class BadImage(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def process(raw):
    """bytes -> (webp bytes, mime, version). Raises BadImage."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise BadImage(TOO_LARGE, 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:      # the real type comes from the file's contents, not its name
                if probe.format not in FORMATS:
                    raise BadImage(NOT_IMAGE)
                probe.verify()
            img = Image.open(io.BytesIO(raw))
            img.load()
    except BadImage:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, SyntaxError, ValueError):
        raise BadImage(NOT_IMAGE)
    img = ImageOps.exif_transpose(img)            # phone photos: turn the right way up before the EXIF data is dropped
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA" if has_alpha else "RGB")
    img.info = {}                                 # drop EXIF (GPS, camera), ICC and comments carried over from the upload
    out = io.BytesIO()
    img.save(out, "WEBP", quality=80, method=6)   # no exif= / icc_profile= passed, so no metadata is written
    data = out.getvalue()
    return data, "image/webp", hashlib.sha256(data).hexdigest()[:12]
