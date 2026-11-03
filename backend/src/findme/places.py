from __future__ import annotations

import os
import time

import httpx

from findme.upstream import Circuit, UpstreamDown, emit_external

AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
DETAILS_URL = "https://places.googleapis.com/v1/places"
HOST = "places.googleapis.com"

circuit = Circuit("places")

TIMEOUT_S = 3.0


async def _post_json(client: httpx.AsyncClient, url: str, headers: dict, body: dict, trace=None, request_id: str = "") -> dict:
    if circuit.state == "open":
        emit_external(trace, "places", level="warn", request_id=request_id, host=HOST, skipped="circuit-open")
        raise UpstreamDown("places circuit open")
    started = time.monotonic()
    try:
        resp = await client.post(url, headers=headers, json=body, timeout=TIMEOUT_S)
        ms = round((time.monotonic() - started) * 1000)
        if resp.status_code >= 400:
            circuit.trip()
            emit_external(trace, "places", level="error", request_id=request_id, host=HOST, status=resp.status_code, ms=ms)
            raise UpstreamDown(f"places {resp.status_code}")
        emit_external(trace, "places", request_id=request_id, host=HOST, status=resp.status_code, ms=ms)
        return resp.json()
    except httpx.HTTPError as e:
        circuit.trip()
        ms = round((time.monotonic() - started) * 1000)
        emit_external(trace, "places", level="error", request_id=request_id, host=HOST, ms=ms, error=type(e).__name__)
        raise UpstreamDown(str(e))


async def autocomplete(client: httpx.AsyncClient, query: str, session: str, trace=None, request_id: str = "") -> dict:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        return {"suggestions": [], "degraded": "upstream-failed"}
    try:
        data = await _post_json(
            client,
            AUTOCOMPLETE_URL,
            {"X-Goog-Api-Key": key},
            {"input": query, "sessionToken": session},
            trace=trace,
            request_id=request_id,
        )
    except UpstreamDown:
        return {"suggestions": [], "degraded": "upstream-failed"}
    out = []
    for s in data.get("suggestions", [])[:8]:
        p = s.get("placePrediction") or {}
        place_id = p.get("placeId")
        label = (p.get("text") or {}).get("text", "")
        if place_id:
            out.append({"placeId": place_id, "label": label})
    return {"suggestions": out}


async def details(client: httpx.AsyncClient, place_id: str, session: str, trace=None, request_id: str = "") -> dict | None:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        return None
    if circuit.state == "open":
        emit_external(trace, "places", level="warn", request_id=request_id, host=HOST, skipped="circuit-open")
        return None
    headers = {
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "id,displayName,formattedAddress,location",
    }
    started = time.monotonic()
    try:
        resp = await client.get(f"{DETAILS_URL}/{place_id}", headers=headers, params={"sessionToken": session}, timeout=TIMEOUT_S)
        ms = round((time.monotonic() - started) * 1000)
        if resp.status_code >= 400:
            circuit.trip()
            emit_external(trace, "places", level="error", request_id=request_id, host=HOST, status=resp.status_code, ms=ms)
            return None
        emit_external(trace, "places", request_id=request_id, host=HOST, status=resp.status_code, ms=ms)
        data = resp.json()
    except httpx.HTTPError as e:
        circuit.trip()
        emit_external(trace, "places", level="error", request_id=request_id, host=HOST, error=type(e).__name__)
        return None
    loc = data.get("location") or {}
    if "latitude" not in loc:
        return None
    label = (data.get("displayName") or {}).get("text") or data.get("formattedAddress") or place_id
    return {"placeId": place_id, "label": label, "lat": loc["latitude"], "lon": loc["longitude"]}
