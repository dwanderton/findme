from __future__ import annotations

import io

from PIL import Image, ImageOps

THUMB_PX = 400
NORMALIZE_PX = 2048
DEDUPE_HAMMING = 4


def dhash(data: bytes) -> int:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("L").resize((9, 8), Image.LANCZOS)
    px = list(img.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def dedupe(items: list[tuple[str, bytes]]) -> tuple[list[str], list[str]]:
    kept: list[tuple[str, int]] = []
    dropped: list[str] = []
    for name, data in items:
        try:
            h = dhash(data)
        except Exception:
            kept.append((name, -1))
            continue
        if any(prev >= 0 and hamming(h, prev) <= DEDUPE_HAMMING for _, prev in kept):
            dropped.append(name)
        else:
            kept.append((name, h))
    return [n for n, _ in kept], dropped


def normalize(data: bytes, max_px: int = NORMALIZE_PX) -> bytes:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    w, h = img.size
    if max(w, h) > max_px:
        scale = max_px / max(w, h)
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def thumbnail(data: bytes, max_px: int = THUMB_PX) -> bytes:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=80)
    return buf.getvalue()
