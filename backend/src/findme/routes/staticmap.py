from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Query, Response

from findme.errors import ApiError

router = APIRouter()

STATIC_URL = "https://maps.googleapis.com/maps/api/staticmap"

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
    lat: float = Query(...),
    lon: float = Query(...),
    zoom: int = Query(14, ge=1, le=20),
):
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        raise ApiError("UPSTREAM_FACE_ENGINE", "Static maps unavailable.")
    params = [
        ("center", f"{lat},{lon}"),
        ("zoom", str(zoom)),
        ("size", "640x360"),
        ("scale", "2"),
        ("markers", f"color:0x5D29F0|{lat},{lon}"),
        ("key", key),
    ]
    params += [("style", s) for s in DARK_STYLE]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(STATIC_URL, params=params, timeout=8.0)
    except httpx.HTTPError:
        raise ApiError("UPSTREAM_FACE_ENGINE", "Static map fetch failed.")
    if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image"):
        raise ApiError("UPSTREAM_FACE_ENGINE", "Static map unavailable.")
    return Response(
        content=resp.content,
        media_type=resp.headers.get("content-type", "image/png"),
        headers={"Cache-Control": "public, max-age=86400"},
    )
