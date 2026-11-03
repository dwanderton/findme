from __future__ import annotations

import os

import httpx

from findme.upstream import Circuit, UpstreamDown, get_json

AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

circuit = Circuit("places")


async def autocomplete(client: httpx.AsyncClient, query: str, session: str) -> dict:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        return {"suggestions": [], "degraded": "upstream-failed"}
    try:
        data = await get_json(
            client,
            circuit,
            AUTOCOMPLETE_URL,
            {"input": query, "sessiontoken": session, "key": key},
        )
    except UpstreamDown:
        return {"suggestions": [], "degraded": "upstream-failed"}
    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        return {"suggestions": [], "degraded": "upstream-failed"}
    return {
        "suggestions": [
            {"placeId": p["place_id"], "label": p.get("description", "")}
            for p in data.get("predictions", [])[:8]
        ]
    }


async def details(client: httpx.AsyncClient, place_id: str, session: str) -> dict | None:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        return None
    try:
        data = await get_json(
            client,
            circuit,
            DETAILS_URL,
            {"place_id": place_id, "sessiontoken": session, "fields": "name,formatted_address,geometry", "key": key},
        )
    except UpstreamDown:
        return None
    result = data.get("result") or {}
    loc = (result.get("geometry") or {}).get("location") or {}
    if "lat" not in loc:
        return None
    label = result.get("name") or result.get("formatted_address") or place_id
    return {"placeId": place_id, "label": label, "lat": loc["lat"], "lon": loc["lng"]}
