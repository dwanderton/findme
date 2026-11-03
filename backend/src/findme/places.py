from __future__ import annotations

import os

import httpx

from findme.upstream import Circuit, UpstreamDown

AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
DETAILS_URL = "https://places.googleapis.com/v1/places"

circuit = Circuit("places")

TIMEOUT_S = 3.0


async def _post_json(client: httpx.AsyncClient, url: str, headers: dict, body: dict) -> dict:
    if circuit.state == "open":
        raise UpstreamDown("places circuit open")
    try:
        resp = await client.post(url, headers=headers, json=body, timeout=TIMEOUT_S)
        if resp.status_code >= 400:
            circuit.trip()
            raise UpstreamDown(f"places {resp.status_code}")
        return resp.json()
    except httpx.HTTPError as e:
        circuit.trip()
        raise UpstreamDown(str(e))


async def autocomplete(client: httpx.AsyncClient, query: str, session: str) -> dict:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        return {"suggestions": [], "degraded": "upstream-failed"}
    try:
        data = await _post_json(
            client,
            AUTOCOMPLETE_URL,
            {"X-Goog-Api-Key": key},
            {"input": query, "sessionToken": session},
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


async def details(client: httpx.AsyncClient, place_id: str, session: str) -> dict | None:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        return None
    if circuit.state == "open":
        return None
    headers = {
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "id,displayName,formattedAddress,location",
    }
    try:
        resp = await client.get(f"{DETAILS_URL}/{place_id}", headers=headers, params={"sessionToken": session}, timeout=TIMEOUT_S)
        if resp.status_code >= 400:
            circuit.trip()
            return None
        data = resp.json()
    except httpx.HTTPError:
        circuit.trip()
        return None
    loc = data.get("location") or {}
    if "latitude" not in loc:
        return None
    label = (data.get("displayName") or {}).get("text") or data.get("formattedAddress") or place_id
    return {"placeId": place_id, "label": label, "lat": loc["latitude"], "lon": loc["longitude"]}
