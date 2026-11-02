from __future__ import annotations

import io

from PIL import Image

from findme.errors import ApiError

Image.MAX_IMAGE_PIXELS = 50_000_000

MAX_SELFIES = 5
MAX_SELFIE_BYTES = 8 * 1024 * 1024
MAX_PHOTO_BYTES = 20 * 1024 * 1024
MAX_PHOTOS = 5000
BATCH_MAX_PHOTOS = 8
BATCH_MAX_BYTES = 8 * 1024 * 1024

MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
}


def sniff(data: bytes) -> str | None:
    for magic, mime in MAGIC.items():
        if data.startswith(magic):
            return mime
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) > 12 and data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1"):
        return "image/heic"
    return None


def check_image(data: bytes, max_bytes: int = MAX_PHOTO_BYTES, name: str = "") -> str:
    if len(data) > max_bytes:
        raise ApiError("BODY_TOO_LARGE", f"{name or 'file'} exceeds {max_bytes} bytes.", name=name)
    mime = sniff(data)
    if mime is None:
        raise ApiError("UNSUPPORTED_MEDIA", f"{name or 'file'} is not jpeg/png/webp/heic.", name=name)
    return mime


def check_decodable(data: bytes) -> tuple[int, int]:
    try:
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        if w * h > Image.MAX_IMAGE_PIXELS:
            raise ApiError("UNSUPPORTED_MEDIA", "Image exceeds the 50 MP decode guard.")
        img.verify()
        return (w, h)
    except ApiError:
        raise
    except Image.DecompressionBombError:
        raise ApiError("UNSUPPORTED_MEDIA", "Image exceeds the 50 MP decode guard.")
    except Exception:
        raise ApiError("UNSUPPORTED_MEDIA", "Image failed to decode.")


def check_selfie_count(existing: int, adding: int) -> None:
    total = existing + adding
    if adding < 1:
        raise ApiError("NO_FACE_IN_SELFIE", "At least one selfie is required.")
    if total > MAX_SELFIES:
        raise ApiError(
            "TOO_MANY_SELFIES",
            f"Reference set caps at {MAX_SELFIES} selfies (have {existing}, adding {adding}).",
        )
