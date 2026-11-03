import io

import pytest
from PIL import Image

from findme.errors import ApiError
from findme.validate import check_decodable, check_image, check_selfie_count, sniff
from tests.fixtures import jpeg


def test_sniff_jpeg_png_webp():
    assert sniff(jpeg()) == "image/jpeg"
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "PNG")
    assert sniff(buf.getvalue()) == "image/png"
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "WEBP")
    assert sniff(buf.getvalue()) == "image/webp"


def test_sniff_avif():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "AVIF")
    data = buf.getvalue()
    assert sniff(data) == "image/avif"
    assert check_decodable(data) == (4, 4)


def test_lying_extension_rejected():
    with pytest.raises(ApiError) as e:
        check_image(b"GIF89a" + b"\x00" * 64, name="x.jpg")
    assert e.value.code == "UNSUPPORTED_MEDIA"


def test_size_cap():
    with pytest.raises(ApiError) as e:
        check_image(jpeg(), max_bytes=10, name="big.jpg")
    assert e.value.code == "BODY_TOO_LARGE"


def test_decode_bomb_guard():
    buf = io.BytesIO()
    Image.new("L", (12000, 5000)).save(buf, "PNG")
    with pytest.raises(ApiError):
        check_decodable(buf.getvalue())


def test_valid_decodes():
    assert check_decodable(jpeg(64, 48)) == (64, 48)


def test_selfie_counts():
    check_selfie_count(0, 1)
    check_selfie_count(4, 1)
    with pytest.raises(ApiError) as e:
        check_selfie_count(5, 1)
    assert e.value.code == "TOO_MANY_SELFIES"
    with pytest.raises(ApiError):
        check_selfie_count(0, 6)
    with pytest.raises(ApiError):
        check_selfie_count(0, 0)
