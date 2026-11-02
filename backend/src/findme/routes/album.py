from __future__ import annotations

from fastapi import APIRouter, Request

from findme.albums import create_album, load_meta, save_meta
from findme.jobs.index_cpu import run_cpu_stage

router = APIRouter()


@router.post("/albums", status_code=201)
async def post_album(request: Request):
    body = await request.json()
    meta = create_album(request.app.state.root, int(body.get("photoCount", 0)))
    return {
        "albumId": meta["albumId"],
        "ownerToken": meta["ownerToken"],
        "upload": {"url": "/upload", "batchMaxBytes": 8_000_000, "batchMaxPhotos": 8},
    }


@router.post("/albums/{album_id}/commit", status_code=202)
async def commit(album_id: str, request: Request):
    root = request.app.state.root
    meta = load_meta(root, album_id)
    meta["committed"] = True
    save_meta(root, meta)
    runner = getattr(request.app.state, "run_index", None)
    if runner:
        result = runner(root, album_id)
    else:
        result = run_cpu_stage(root, album_id)
    return {"albumId": album_id, "accepted": result["accepted"], "rejected": result["rejected"]}
