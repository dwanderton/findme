from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request

from findme.albums import gps_coverage, load_meta
from findme.enrich import Enricher
from findme.errors import ApiError
from findme.exif import camera_panel
from findme.faces import load_refs
from findme.match import search
from findme.schemas import ExifData, Vlm, clean
from findme.store import index_mtime, load_index
from findme.trace import TraceWriter
from findme.vlm import VlmClient

router = APIRouter()

_index_cache: dict[str, tuple[float, tuple]] = {}


def _cached_index(root, album_id: str):
    mtime = index_mtime(root, album_id)
    hit = _index_cache.get(album_id)
    if hit and hit[0] == mtime:
        return hit[1]
    data = load_index(root, album_id)
    _index_cache[album_id] = (mtime, data)
    return data


@router.get("/find")
async def find(request: Request, userId: str, albumId: str, threshold: str = "strong"):
    root = request.app.state.root
    meta = load_meta(root, albumId)
    if meta.get("stage") != "ready":
        raise ApiError("INDEX_NOT_READY", f"Album is {meta.get('stage')}; try again shortly.")
    refs = load_refs(root, userId)
    emb, face_px, photo_ids, bboxes = _cached_index(root, albumId)

    import numpy as np

    unique_photos = sorted(set(photo_ids))
    photo_to_int = {p: i for i, p in enumerate(unique_photos)}
    img_idx = np.array([photo_to_int[p] for p in photo_ids], dtype=np.int64)

    matches, refs_used = search(emb, face_px, img_idx, refs)
    if threshold == "strong":
        matches = [m for m in matches if m.band == "strong"]

    trace = TraceWriter(root, albumId, "find")
    trace.emit("find", "search.done", matches=len(matches), refs=refs_used)

    enricher = Enricher(root, albumId, venue=meta.get("venue"))
    vlm = VlmClient(root, albumId)
    vlm_available = bool(os.environ.get("VLM_BASE_URL")) or getattr(request.app.state, "run_vlm", None)

    out, e_summary, v_summary = [], {"full": 0, "partial": 0, "scrubbed": 0, "upstreamFailed": 0}, {"ready": 0, "pending": 0, "unavailable": 0}
    pending_vlm: list[str] = []
    async with httpx.AsyncClient() as client:
        for m in matches:
            photo_id = photo_ids[m.face_row]
            info = meta["photos"].get(photo_id, {})
            exif = ExifData(**info.get("exif", {})) if info.get("exif") else ExifData()
            enriched = await enricher.enrich(client, exif)
            key = {
                "full": "full",
                "partial": "partial",
                "metadata-scrubbed": "scrubbed",
                "upstream-failed": "upstreamFailed",
                "deferred": "partial",
            }[enriched.status]
            e_summary[key] += 1

            cached = vlm.cached(photo_id)
            if cached:
                vrec = Vlm(**cached)
                v_summary["ready"] += 1
            elif vlm_available:
                vrec = Vlm(status="pending")
                v_summary["pending"] += 1
                pending_vlm.append(photo_id)
            else:
                vrec = Vlm(status="unavailable")
                v_summary["unavailable"] += 1

            out.append(
                {
                    "photoId": photo_id,
                    "score": m.score,
                    "band": m.band,
                    "bbox": list(bboxes[m.face_row]),
                    "thumbUrl": f"/photos/{photo_id}?userId={userId}&albumId={albumId}&thumb=true",
                    "fullUrl": f"/photos/{photo_id}?userId={userId}&albumId={albumId}",
                    "takenAt": exif.taken_at,
                    "camera": clean(camera_panel(exif)),
                    "place": clean(enriched.place),
                    "weather": clean(enriched.weather),
                    "vlm": clean(vrec),
                    "enrichment": {"status": enriched.status},
                }
            )

    story_text = vlm.cached_story([m["photoId"] for m in out])
    if story_text:
        story = {"status": "ready", "text": story_text}
    elif out and vlm_available:
        story = {"status": "pending"}
    else:
        story = {"status": "unavailable"}

    runner = getattr(request.app.state, "run_vlm", None)
    if pending_vlm and runner:
        runner(root, albumId, userId, pending_vlm, [m["photoId"] for m in out])

    matched_ids = {m["photoId"] for m in out}
    if hasattr(request.app.state, "find_grants"):
        request.app.state.find_grants.setdefault(userId, set()).update(matched_ids)

    return {
        "album": {"id": albumId, "photos": len(meta["photos"]), "faces": int(emb.shape[0])},
        "matches": out,
        "story": story,
        "enrichmentSummary": e_summary,
        "vlmSummary": v_summary,
        "gpsCoverage": gps_coverage(meta),
    }
