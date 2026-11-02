from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from findme.errors import ApiError
from findme.store import album_dir


def meta_path(root: Path, album_id: str) -> Path:
    return album_dir(root, album_id) / "meta.json"


def _write_meta(root: Path, album_id: str, meta: dict) -> None:
    p = meta_path(root, album_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta))
    tmp.replace(p)


def create_album(root: Path, photo_count: int) -> dict:
    if photo_count < 1 or photo_count > 5000:
        raise ApiError("ALBUM_TOO_LARGE", f"photoCount must be 1-5000, got {photo_count}.")
    album_id = str(uuid.uuid4())
    owner_token = str(uuid.uuid4())
    meta = {
        "albumId": album_id,
        "ownerToken": owner_token,
        "photoCount": photo_count,
        "committed": False,
        "stage": "received",
        "venue": None,
        "photos": {},
    }
    _write_meta(root, album_id, meta)
    (album_dir(root, album_id) / "photos").mkdir(parents=True, exist_ok=True)
    return meta


def load_meta(root: Path, album_id: str) -> dict:
    p = meta_path(root, album_id)
    if not p.exists():
        raise ApiError("UNKNOWN_ALBUM", "Album not found.")
    return json.loads(p.read_text())


def save_meta(root: Path, meta: dict) -> None:
    _write_meta(root, meta["albumId"], meta)


def require_owner(meta: dict, token: str | None) -> None:
    if not token or token != meta["ownerToken"]:
        raise ApiError("FORBIDDEN", "Owner token required.")


def set_venue(root: Path, album_id: str, token: str | None, venue: dict | None) -> dict:
    meta = load_meta(root, album_id)
    require_owner(meta, token)
    meta["venue"] = venue
    save_meta(root, meta)
    return meta


def gps_coverage(meta: dict) -> dict:
    photos = meta.get("photos", {})
    with_gps = sum(1 for p in photos.values() if p.get("exif", {}).get("gps_present"))
    return {"withGps": with_gps, "total": len(photos)}


def delete_album(root: Path, album_id: str, token: str | None) -> None:
    meta = load_meta(root, album_id)
    require_owner(meta, token)
    shutil.rmtree(album_dir(root, album_id), ignore_errors=True)
    shutil.rmtree(root / "enrich" / album_id, ignore_errors=True)


def delete_user(root: Path, user_id: str) -> None:
    p = root / "faces" / f"{user_id}.npy"
    p.unlink(missing_ok=True)
