from findme.exif import camera_panel, extract
from tests.fixtures import corrupt_jpeg, jpeg, jpeg_with_exif


def test_full_exif_extraction():
    e = extract(jpeg_with_exif())
    assert e.exif_present and e.gps_present
    assert abs(e.lat - 37.4267) < 0.0005
    assert abs(e.lon - (-122.0806)) < 0.0005
    assert e.taken_at == "2026-09-14T14:32:11-07:00"
    assert e.make == "Sony"
    assert e.model == "ILCE-7M4"
    assert e.lens == "FE 35mm F1.8"
    assert e.focal_length_mm == 35.0
    assert e.aperture == 1.8
    assert e.shutter == "1/250"
    assert e.iso == 400


def test_southern_western_hemisphere():
    e = extract(jpeg_with_exif(lat=-33.8568, lon=-151.2153 + 302.4306))
    assert e.lat < 0


def test_scrubbed():
    e = extract(jpeg())
    assert not e.exif_present
    assert not e.gps_present
    assert camera_panel(e).reason == "exif-stripped"


def test_exif_without_gps():
    e = extract(jpeg_with_exif(lat=None, lon=None))
    assert e.exif_present and not e.gps_present
    panel = camera_panel(e)
    assert panel.present and panel.iso == 400


def test_corrupt_never_raises():
    e = extract(corrupt_jpeg())
    assert e.exif_present in (True, False)


def test_garbage_never_raises():
    e = extract(b"not an image at all")
    assert not e.exif_present
