import io

from PIL import Image

from findme.media import dedupe, dhash, hamming, normalize, thumbnail


def gradient_jpeg(width=640, height=480, shift=0) -> bytes:
    img = Image.new("L", (width, height))
    img.putdata([(x + shift) % 256 for y in range(height) for x in range(width)])
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=90)
    return buf.getvalue()


def noise_jpeg(seed: int) -> bytes:
    import random

    rng = random.Random(seed)
    img = Image.new("L", (64, 64))
    img.putdata([rng.randrange(256) for _ in range(64 * 64)])
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=90)
    return buf.getvalue()


def test_near_dupe_collapses_keeping_first():
    a, b = gradient_jpeg(), gradient_jpeg(shift=1)
    assert hamming(dhash(a), dhash(b)) <= 4
    kept, dropped = dedupe([("first.jpg", a), ("second.jpg", b)])
    assert kept == ["first.jpg"]
    assert dropped == ["second.jpg"]


def test_distinct_survive():
    a, b = noise_jpeg(1), noise_jpeg(2)
    assert hamming(dhash(a), dhash(b)) > 4
    kept, dropped = dedupe([("a.jpg", a), ("b.jpg", b)])
    assert kept == ["a.jpg", "b.jpg"] and not dropped


def test_normalize_caps_long_side():
    big = gradient_jpeg(4000, 1000)
    out = Image.open(io.BytesIO(normalize(big)))
    assert max(out.size) == 2048
    small = gradient_jpeg(640, 480)
    out = Image.open(io.BytesIO(normalize(small)))
    assert out.size == (640, 480)


def test_thumbnail_dims_and_format():
    t = thumbnail(gradient_jpeg(1600, 900))
    img = Image.open(io.BytesIO(t))
    assert img.format == "WEBP"
    assert max(img.size) == 400


def test_undecodable_kept_not_raised():
    kept, dropped = dedupe([("bad.jpg", b"garbage"), ("good.jpg", noise_jpeg(3))])
    assert "bad.jpg" in kept and not dropped
