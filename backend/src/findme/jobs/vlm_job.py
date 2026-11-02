from __future__ import annotations

from pathlib import Path

import httpx

from findme.store import album_dir
from findme.trace import TraceWriter
from findme.vlm import VlmClient


async def run_vlm_job(
    root: Path,
    album_id: str,
    user_id: str,
    photo_ids: list[str],
    result_set: list[str],
    client: httpx.AsyncClient | None = None,
    vlm: VlmClient | None = None,
) -> dict:
    vlm = vlm or VlmClient(root, album_id)
    trace = TraceWriter(root, album_id, f"vlm-{user_id[:8]}")
    trace.emit("vlm", "job.start", photos=len(photo_ids))
    photos_dir = album_dir(root, album_id) / "photos"

    own_client = client is None
    client = client or httpx.AsyncClient()
    ready, unavailable = 0, 0
    try:
        for pid in photo_ids:
            p = photos_dir / f"{pid}.jpg"
            if not p.exists():
                unavailable += 1
                continue
            record = await vlm.caption_photo(client, pid, p.read_bytes())
            if record.get("status") == "ready":
                ready += 1
            else:
                unavailable += 1
                trace.emit("vlm", "caption.unavailable", level="warn", photoId=pid)
                break

        story = {"status": "unavailable"}
        if unavailable == 0 and result_set:
            records = []
            for pid in result_set:
                rec = vlm.cached(pid)
                if rec:
                    records.append({"photoId": pid, "caption": rec.get("caption"), "tags": rec.get("tags")})
            story = await vlm.story(client, result_set, records)
    finally:
        if own_client:
            await client.aclose()

    trace.emit("vlm", "job.done", ready=ready, unavailable=unavailable, story=story.get("status"))
    return {"ready": ready, "unavailable": unavailable, "story": story.get("status")}
