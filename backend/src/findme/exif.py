from __future__ import annotations

import io

from PIL import Image, ExifTags

from findme.schemas import Camera, ExifData

Image.MAX_IMAGE_PIXELS = 50_000_000

GPS_IFD = 0x8825


def _ratio(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _dms_to_decimal(dms, ref: str) -> float | None:
    try:
        deg = _ratio(dms[0]) + _ratio(dms[1]) / 60 + _ratio(dms[2]) / 3600
    except (TypeError, IndexError):
        return None
    if ref in ("S", "W"):
        deg = -deg
    return round(deg, 6)


def _shutter(v) -> str | None:
    f = _ratio(v)
    if f <= 0:
        return None
    if f >= 1:
        return f"{f:g}s"
    return f"1/{round(1 / f)}"


def extract(data: bytes) -> ExifData:
    out = ExifData()
    try:
        img = Image.open(io.BytesIO(data))
        raw = img.getexif()
    except Exception:
        return out
    if not raw:
        return out

    out.exif_present = True
    out.orientation = int(raw.get(ExifTags.Base.Orientation, 1) or 1)
    out.make = str(raw.get(ExifTags.Base.Make, "")).strip() or None
    out.model = str(raw.get(ExifTags.Base.Model, "")).strip() or None

    try:
        ifd = raw.get_ifd(ExifTags.IFD.Exif)
    except Exception:
        ifd = {}
    dt = ifd.get(ExifTags.Base.DateTimeOriginal) or raw.get(ExifTags.Base.DateTime)
    if dt:
        offset = ifd.get(ExifTags.Base.OffsetTimeOriginal, "") or ""
        out.taken_at = str(dt).replace(":", "-", 2).replace(" ", "T") + str(offset)
    out.lens = str(ifd.get(ExifTags.Base.LensModel, "")).strip() or None
    fl = ifd.get(ExifTags.Base.FocalLength)
    out.focal_length_mm = round(_ratio(fl), 1) if fl else None
    fn = ifd.get(ExifTags.Base.FNumber)
    out.aperture = round(_ratio(fn), 1) if fn else None
    out.shutter = _shutter(ifd.get(ExifTags.Base.ExposureTime))
    iso = ifd.get(ExifTags.Base.ISOSpeedRatings) or ifd.get(0x8833)
    if isinstance(iso, (tuple, list)):
        iso = iso[0] if iso else None
    out.iso = int(iso) if iso else None

    try:
        gps = raw.get_ifd(GPS_IFD)
    except Exception:
        gps = {}
    if gps:
        lat = _dms_to_decimal(gps.get(2), str(gps.get(1, "N")))
        lon = _dms_to_decimal(gps.get(4), str(gps.get(3, "E")))
        if lat is not None and lon is not None and (lat, lon) != (0.0, 0.0):
            out.lat, out.lon = lat, lon
            out.gps_present = True
    return out


def camera_panel(e: ExifData) -> Camera:
    if not e.exif_present:
        return Camera(present=False, reason="exif-stripped")
    if not any([e.make, e.model, e.aperture, e.shutter, e.iso, e.focal_length_mm]):
        return Camera(present=False, reason="no-camera-fields")
    return Camera(
        present=True,
        make=e.make,
        model=e.model,
        lens=e.lens,
        focalLengthMm=e.focal_length_mm,
        aperture=e.aperture,
        shutter=e.shutter,
        iso=e.iso,
    )
