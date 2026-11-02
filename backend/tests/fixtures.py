from __future__ import annotations

import io
from fractions import Fraction

import piexif
from PIL import Image


def _deg_to_dms(deg: float):
    d = int(abs(deg))
    m_f = (abs(deg) - d) * 60
    m = int(m_f)
    s = Fraction(round((m_f - m) * 60 * 10000), 10000)
    return ((d, 1), (m, 1), (s.numerator, s.denominator))


def jpeg(width=64, height=48, color=(120, 60, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, "JPEG", quality=85)
    return buf.getvalue()


def jpeg_with_exif(
    lat: float | None = 37.4267,
    lon: float | None = -122.0806,
    taken_at: str = "2026:09:14 14:32:11",
    offset: str = "-07:00",
    make: str = "Sony",
    model: str = "ILCE-7M4",
    lens: str = "FE 35mm F1.8",
    focal=(35, 1),
    fnumber=(18, 10),
    exposure=(1, 250),
    iso: int = 400,
) -> bytes:
    zeroth = {
        piexif.ImageIFD.Make: make,
        piexif.ImageIFD.Model: model,
        piexif.ImageIFD.Orientation: 1,
    }
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: taken_at,
        piexif.ExifIFD.OffsetTimeOriginal: offset,
        piexif.ExifIFD.LensModel: lens,
        piexif.ExifIFD.FocalLength: focal,
        piexif.ExifIFD.FNumber: fnumber,
        piexif.ExifIFD.ExposureTime: exposure,
        piexif.ExifIFD.ISOSpeedRatings: iso,
    }
    gps_ifd = {}
    if lat is not None and lon is not None:
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S",
            piexif.GPSIFD.GPSLatitude: _deg_to_dms(lat),
            piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W",
            piexif.GPSIFD.GPSLongitude: _deg_to_dms(lon),
        }
    exif_bytes = piexif.dump({"0th": zeroth, "Exif": exif_ifd, "GPS": gps_ifd})
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 10, 30)).save(buf, "JPEG", exif=exif_bytes)
    return buf.getvalue()


def corrupt_jpeg() -> bytes:
    good = jpeg()
    return good[: len(good) // 2]
