from __future__ import annotations

from pathlib import Path

from findme import settings
from findme.albums import load_meta, save_meta
from findme.exif import extract
from findme.media import dedupe, normalize, thumbnail
from findme.schemas import ExifData
from findme.store import album_dir, write_counter
from findme.trace import TraceWriter
from findme.validate import check_decodable


def _merge_exif(file_exif: ExifData, client: dict | None) -> ExifData:
    if not client:
        return file_exif
    merged = file_exif
    if client.get("gps_present") and not merged.gps_present:
        merged.gps_present = True
        merged.lat = client.get("lat")
        merged.lon = client.get("lon")
    if client.get("taken_at") and not merged.taken_at:
        merged.taken_at = client["taken_at"]
    if client.get("file_modified"):
        merged.file_modified = client["file_modified"]
    for field in ("make", "model", "lens", "shutter"):
        if client.get(field) and not getattr(merged, field):
            setattr(merged, field, client[field])
    for field in ("focal_length_mm", "aperture", "iso"):
        if client.get(field) and not getattr(merged, field):
            setattr(merged, field, client[field])
    if client.get("gps_present") or client.get("taken_at") or client.get("make"):
        merged.exif_present = True
    return merged


def run_cpu_stage(root: Path, album_id: str) -> dict:
    trace = TraceWriter(root, album_id, "cpu-index")
    trace.emit("cpu-qb", "extract.start")
    meta = load_meta(root, album_id)
    photos_dir = album_dir(root, album_id) / "photos"
    thumbs_dir = album_dir(root, album_id) / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    meta["stage"] = "extracting"
    save_meta(root, meta)

    items, failures = [], []
    for photo_id, info in meta["photos"].items():
        p = photos_dir / f"{photo_id}.jpg"
        if not p.exists():
            failures.append(photo_id)
            continue
        data = p.read_bytes()
        try:
            check_decodable(data)
        except Exception:
            failures.append(photo_id)
            trace.emit("cpu-qb", "photo.skipped", level="warn", photoId=photo_id)
            continue
        items.append((photo_id, data))

    kept_ids, dropped = dedupe(items)
    kept = [(pid, data) for pid, data in items if pid in set(kept_ids)]

    done = 0
    for photo_id, data in kept:
        exif = _merge_exif(extract(data), meta["photos"][photo_id].get("clientExif"))
        meta["photos"][photo_id]["exif"] = exif.__dict__
        normalized = normalize(data)
        (photos_dir / f"{photo_id}.jpg").write_bytes(normalized)
        (thumbs_dir / f"{photo_id}.webp").write_bytes(thumbnail(normalized))
        done += 1
        if done % 25 == 0:
            write_counter(root, album_id, "extracting", "cpu", {"photosDone": done, "photosTotal": len(kept)})

    for photo_id in dropped + failures:
        meta["photos"].pop(photo_id, None)
        (photos_dir / f"{photo_id}.jpg").unlink(missing_ok=True)

    ids = [pid for pid, _ in kept]
    batches = [ids[i : i + settings.BATCH_SIZE] for i in range(0, len(ids), settings.BATCH_SIZE)]
    meta["stage"] = "embedding"
    meta["batches"] = {str(i): {"photos": b, "done": False} for i, b in enumerate(batches)}
    save_meta(root, meta)
    write_counter(root, album_id, "extracting", "cpu", {"photosDone": done, "photosTotal": len(kept)})
    trace.emit("cpu-qb", "extract.done", accepted=len(kept), dropped=len(dropped), failed=len(failures))
    return {
        "accepted": len(kept),
        "rejected": [{"name": pid, "reason": "duplicate"} for pid in dropped]
        + [{"name": pid, "reason": "undecodable"} for pid in failures],
        "batches": len(batches),
    }
