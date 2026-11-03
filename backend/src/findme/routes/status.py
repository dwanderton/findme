from __future__ import annotations

from fastapi import APIRouter, Request

from findme import settings
from findme.albums import gps_coverage, load_meta
from findme.errors import ApiError
from findme.store import aggregate_counters
from findme.trace import read_merged

router = APIRouter()

STAGES = ["received", "extracting", "embedding", "ready"]


@router.get("/albums/{album_id}/status")
async def album_status(album_id: str, request: Request):
    root = request.app.state.root
    meta = load_meta(root, album_id)
    counters = aggregate_counters(root, album_id)
    total = len(meta.get("photos", {}))
    stage = meta.get("stage", "received")
    if stage == "embedding":
        done = counters.get("embedding", {}).get("photosDone", 0)
    elif stage in ("ready", "failed"):
        done = total
    else:
        done = counters.get("extracting", {}).get("photosDone", 0)
    return {
        "stage": stage,
        "photosTotal": total,
        "photosDone": int(done),
        "facesFound": int(counters.get("embedding", {}).get("facesFound", 0)),
        "stages": STAGES,
        "gpsCoverage": gps_coverage(meta),
        "venue": meta.get("venue"),
        "startedAt": None,
        "error": meta.get("error"),
    }


@router.get("/debug/{album_id}")
async def debug_trace(album_id: str, request: Request, cursor: int = 0):
    if not settings.DEBUG_UI:
        raise ApiError("UNKNOWN_ALBUM", "Not found.")
    root = request.app.state.root
    load_meta(root, album_id)
    events, new_cursor = read_merged(root, album_id, cursor=cursor)
    for e in events:
        e["level"] = e.get("level", "info")
        e["src"] = e.get("src", "unknown")
    snapshot = {
        "endpointHealth": getattr(request.app.state, "health_snapshot", lambda: {})() or {},
        "rateLimit": {"windowRemaining": None, "windowMax": None},
        "circuits": _circuits(),
        "enrichBudget": {"used": None, "max": 50},
    }
    return {"cursor": new_cursor, "events": events, "snapshot": snapshot}


def _circuits() -> dict:
    import findme.geo as geo
    import findme.weather as weather

    return {"google": geo.circuit.state, "open-meteo": weather.circuit.state}
