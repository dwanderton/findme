from __future__ import annotations

import os
import time

import httpx
from fastapi import APIRouter, Query, Request, Response

from findme.errors import ApiError
from findme.trace import writer_for
from findme.upstream import Circuit, emit_external

router = APIRouter()

STATIC_URL = "https://maps.googleapis.com/maps/api/staticmap"
HOST = "maps.googleapis.com"
TIMEOUT_S = 8.0

circuit = Circuit("staticmap")

# Compact dark map style tuned to the app's violet-black surfaces.
DARK_STYLE = [
    "feature:all|element:geometry|color:0x16111f",
    "feature:all|element:labels.text.fill|color:0x8b849e",
    "feature:all|element:labels.text.stroke|color:0x16111f",
    "feature:road|element:geometry|color:0x2a2340",
    "feature:water|element:geometry|color:0x0f1a33",
    "feature:poi|element:geometry|color:0x1d1830",
]


@router.get("/staticmap")
async def staticmap(
    request: Request,
    lat: float = Query(...),
    lon: float = Query(...),
    zoom: int = Query(14, ge=1, le=20),
    albumId: str | None = Query(default=None),
):
    trace = writer_for(request.app.state.root, albumId, "staticmap")
    rid = request.headers.get("x-request-id", "")
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        raise ApiError("UPSTREAM_MAPS", "Static maps unavailable.")
    if circuit.state == "open":
        emit_external(trace, "staticmap", level="warn", request_id=rid, host=HOST, skipped="circuit-open")
        raise ApiError("UPSTREAM_MAPS", "Static maps unavailable.")
    params = [
        ("center", f"{lat},{lon}"),
        ("zoom", str(zoom)),
        ("size", "640x360"),
        ("scale", "2"),
        ("markers", f"color:0x5D29F0|{lat},{lon}"),
        ("key", key),
    ]
    params += [("style", s) for s in DARK_STYLE]
    started = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(STATIC_URL, params=params, timeout=TIMEOUT_S)
    except httpx.HTTPError as e:
        circuit.trip()
        ms = round((time.monotonic() - started) * 1000)
        emit_external(trace, "staticmap", level="error", request_id=rid, host=HOST, ms=ms, error=type(e).__name__)
        raise ApiError("UPSTREAM_MAPS", "Static map fetch failed.")
    ms = round((time.monotonic() - started) * 1000)
    if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image"):
        circuit.trip()
        emit_external(trace, "staticmap", level="error", request_id=rid, host=HOST, status=resp.status_code, ms=ms)
        raise ApiError("UPSTREAM_MAPS", "Static map unavailable.")
    emit_external(trace, "staticmap", request_id=rid, host=HOST, status=resp.status_code, ms=ms)
    return Response(
        content=resp.content,
        media_type=resp.headers.get("content-type", "image/png"),
        headers={"Cache-Control": "public, max-age=86400"},
    )
