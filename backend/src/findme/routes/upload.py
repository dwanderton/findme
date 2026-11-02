from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Request

from findme import settings
from findme.albums import load_meta, save_meta
from findme.errors import ApiError
from findme.store import album_dir
from findme.validate import BATCH_MAX_BYTES, BATCH_MAX_PHOTOS, sniff

router = APIRouter()


@router.post("/upload")
async def upload_batch(request: Request):
    root = request.app.state.root
    form = await request.form()
    album_id = form.get("albumId")
    if not album_id:
        raise ApiError("UNKNOWN_ALBUM", "albumId is required.")
    meta = load_meta(root, str(album_id))
    if meta["committed"]:
        raise ApiError("ALBUM_TOO_LARGE", "Album already committed; create a new album.")

    files = [(k, v) for k, v in form.multi_items() if hasattr(v, "read")]
    if len(files) > BATCH_MAX_PHOTOS:
        raise ApiError("BODY_TOO_LARGE", f"Batch caps at {BATCH_MAX_PHOTOS} photos.")
    if len(meta["photos"]) + len(files) > settings.MAX_PHOTOS:
        raise ApiError("ALBUM_TOO_LARGE", f"Album caps at {settings.MAX_PHOTOS} photos.")

    photos_dir = album_dir(root, meta["albumId"]) / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    stored, rejected, total_bytes = 0, [], 0
    for key, f in files:
        data = await f.read()
        total_bytes += len(data)
        if total_bytes > BATCH_MAX_BYTES:
            raise ApiError("BODY_TOO_LARGE", f"Batch caps at {BATCH_MAX_BYTES} bytes.")
        name = f.filename or key
        if sniff(data) is None:
            rejected.append({"name": name, "reason": "UNSUPPORTED_MEDIA"})
            continue
        photo_id = str(uuid.uuid4())
        (photos_dir / f"{photo_id}.jpg").write_bytes(data)
        exif_raw = form.get(f"exif_{key}")
        client_exif = None
        if exif_raw:
            try:
                client_exif = json.loads(str(exif_raw))
            except json.JSONDecodeError:
                client_exif = None
        meta["photos"][photo_id] = {"name": name, "clientExif": client_exif}
        stored += 1

    save_meta(root, meta)
    return {"stored": stored, "rejected": rejected}
