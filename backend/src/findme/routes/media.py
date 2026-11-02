from __future__ import annotations

import io
import json
import zipfile
from fractions import Fraction

import piexif
from fastapi import APIRouter, Request, Response

from findme import settings
from findme.albums import load_meta
from findme.errors import ApiError
from findme.faces import load_refs
from findme.store import album_dir
from findme.vlm import VlmClient

router = APIRouter()


def _grants(request: Request) -> dict:
    if not hasattr(request.app.state, "find_grants"):
        request.app.state.find_grants = {}
    return request.app.state.find_grants


def _require_access(request: Request, root, user_id: str, album_id: str, photo_id: str) -> None:
    load_refs(root, user_id)
    meta = load_meta(root, album_id)
    if photo_id not in meta.get("photos", {}):
        raise ApiError("UNKNOWN_PHOTO", "Photo not found.")
    granted = _grants(request).get(user_id)
    if granted is not None and photo_id not in granted:
        raise ApiError("UNKNOWN_PHOTO", "Photo not found.")


@router.get("/photos/{photo_id}")
async def get_photo(photo_id: str, request: Request, userId: str, albumId: str, thumb: bool = False):
    root = request.app.state.root
    _require_access(request, root, userId, albumId, photo_id)
    base = album_dir(root, albumId)
    path = (base / "thumbs" / f"{photo_id}.webp") if thumb else (base / "photos" / f"{photo_id}.jpg")
    if not path.exists():
        raise ApiError("UNKNOWN_PHOTO", "Photo not found.")
    media = "image/webp" if thumb else "image/jpeg"
    return Response(content=path.read_bytes(), media_type=media, headers={"Cache-Control": "private, max-age=3600"})


def _deg_to_dms(deg: float):
    d = int(abs(deg))
    m_f = (abs(deg) - d) * 60
    m = int(m_f)
    s = Fraction(round((m_f - m) * 60 * 10000), 10000)
    return ((d, 1), (m, 1), (s.numerator, s.denominator))


def _write_venue_exif(data: bytes, venue: dict) -> bytes:
    gps = {
        piexif.GPSIFD.GPSLatitudeRef: "N" if venue["lat"] >= 0 else "S",
        piexif.GPSIFD.GPSLatitude: _deg_to_dms(venue["lat"]),
        piexif.GPSIFD.GPSLongitudeRef: "E" if venue["lon"] >= 0 else "W",
        piexif.GPSIFD.GPSLongitude: _deg_to_dms(venue["lon"]),
    }
    zeroth = {piexif.ImageIFD.ImageDescription: f"Venue: {venue['label']} (user-supplied)".encode()}
    try:
        exif_bytes = piexif.dump({"0th": zeroth, "GPS": gps})
        return piexif.insert(exif_bytes, data, new_file=None) or data
    except Exception:
        buf = io.BytesIO()
        piexif.insert(piexif.dump({"0th": zeroth, "GPS": gps}), data, buf)
        return buf.getvalue()


def _build_parts(root, album_id: str, user_id: str, photo_ids: list[str]) -> list[bytes]:
    meta = load_meta(root, album_id)
    venue = meta.get("venue")
    vlm = VlmClient(root, album_id)
    base = album_dir(root, album_id) / "photos"

    sidecar = {
        "albumId": album_id,
        "userId": user_id,
        "venue": venue,
        "photos": [
            {
                "photoId": pid,
                "name": meta["photos"][pid].get("name"),
                "exif": meta["photos"][pid].get("exif"),
                "vlm": vlm.cached(pid),
            }
            for pid in photo_ids
        ],
    }

    entries: list[tuple[str, bytes]] = [("findme.json", json.dumps(sidecar, indent=2).encode())]
    for pid in photo_ids:
        p = base / f"{pid}.jpg"
        if not p.exists():
            continue
        data = p.read_bytes()
        exif = meta["photos"][pid].get("exif") or {}
        if venue and not exif.get("gps_present"):
            data = _write_venue_exif(data, venue)
        entries.append((f"photos/{meta['photos'][pid].get('name') or pid}.jpg", data))

    parts, current, size = [], [], 0
    for name, data in entries:
        if current and size + len(data) > settings.ZIP_PART_LIMIT:
            parts.append(current)
            current, size = [], 0
        current.append((name, data))
        size += len(data)
    if current:
        parts.append(current)

    out = []
    for chunk in parts:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in chunk:
                z.writestr(name, data)
        out.append(buf.getvalue())
    return out


@router.get("/albums/{album_id}/download")
async def download(album_id: str, request: Request, userId: str, part: int = 1):
    root = request.app.state.root
    load_refs(root, userId)
    meta = load_meta(root, album_id)
    if meta.get("stage") != "ready":
        raise ApiError("INDEX_NOT_READY", "Index the album first.")
    granted = _grants(request).get(userId)
    if not granted:
        raise ApiError("UNKNOWN_PHOTO", "Run find first; nothing granted to download.")
    photo_ids = sorted(granted)
    parts = _build_parts(root, album_id, userId, photo_ids)
    if part < 1 or part > len(parts):
        raise ApiError("UNKNOWN_PHOTO", f"Part {part} of {len(parts)} not found.")
    return Response(
        content=parts[part - 1],
        media_type="application/zip",
        headers={"X-Parts": str(len(parts)), "Content-Disposition": f'attachment; filename="findme-{album_id[:8]}-part{part}.zip"'},
    )
