from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable

import httpx

from findme.store import album_dir
from findme.trace import TraceWriter
from findme.vlm import VlmClient

CLAIM_TTL_S = 120.0


def claim_photo(vlm_dir: Path, photo_id: str) -> bool:
    claim = vlm_dir / f"{photo_id}.claim"
    try:
        os.close(os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        try:
            if time.time() - claim.stat().st_mtime < CLAIM_TTL_S:
                return False
            claim.touch()
            return True
        except FileNotFoundError:
            return claim_photo(vlm_dir, photo_id)


def release_photo(vlm_dir: Path, photo_id: str) -> None:
    (vlm_dir / f"{photo_id}.claim").unlink(missing_ok=True)


def make_vlm_runner(spawn: Callable[..., None]) -> Callable[..., bool]:
    inflight: set[str] = set()
    lock = threading.Lock()

    def runner(root: Path, album_id: str, user_id: str, photo_ids: list) -> bool:
        with lock:
            if album_id in inflight:
                return False
            inflight.add(album_id)

        def release() -> None:
            with lock:
                inflight.discard(album_id)

        spawn(root, album_id, user_id, photo_ids, release)
        return True

    return runner


async def run_vlm_job(
    root: Path,
    album_id: str,
    user_id: str,
    photo_ids: list[str],
    client: httpx.AsyncClient | None = None,
    vlm: VlmClient | None = None,
) -> dict:
    vlm = vlm or VlmClient(root, album_id)
    trace = TraceWriter(root, album_id, f"vlm-{user_id[:8]}")
    trace.emit("vlm", "job.start", photos=len(photo_ids))
    photos_dir = album_dir(root, album_id) / "photos"

    own_client = client is None
    client = client or httpx.AsyncClient()
    ready, unavailable, skipped = 0, 0, 0
    try:
        for pid in photo_ids:
            p = photos_dir / f"{pid}.jpg"
            if not p.exists():
                unavailable += 1
                continue
            if vlm.cached(pid):
                ready += 1
                continue
            if not claim_photo(vlm.dir, pid):
                skipped += 1
                continue
            try:
                record = await vlm.caption_photo(client, pid, p.read_bytes())
            finally:
                release_photo(vlm.dir, pid)
            if record.get("status") == "ready":
                ready += 1
            else:
                unavailable += 1
                trace.emit("vlm", "caption.unavailable", level="warn", photoId=pid)
                break
    finally:
        if own_client:
            await client.aclose()

    trace.emit("vlm", "job.done", ready=ready, unavailable=unavailable, skipped=skipped)
    return {"ready": ready, "unavailable": unavailable, "skipped": skipped}
