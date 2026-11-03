from __future__ import annotations

import os

import httpx

from findme.schemas import Place
from findme.upstream import Circuit, UpstreamDown, get_json

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
LABEL_PREFERENCE = ("point_of_interest", "neighborhood", "locality")

circuit = Circuit("google")


def _compose(results: list[dict]) -> str | None:
    by_type: dict[str, dict] = {}
    for r in results:
        for t in r.get("types", []):
            by_type.setdefault(t, r)
    for pref in LABEL_PREFERENCE:
        if pref in by_type:
            return by_type[pref].get("formatted_address") or None
    return results[0].get("formatted_address") if results else None


async def reverse_geocode(client: httpx.AsyncClient, lat: float, lon: float, trace=None, request_id: str = "") -> Place:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not key:
        return Place(present=False, reason="no-api-key")
    try:
        data = await get_json(
            client, circuit, GEOCODE_URL, {"latlng": f"{lat},{lon}", "key": key},
            trace=trace, request_id=request_id,
        )
    except UpstreamDown:
        return Place(present=False, reason="upstream-failed")
    status = data.get("status")
    if status == "OVER_QUERY_LIMIT":
        circuit.trip()
        return Place(present=False, reason="rate-limited")
    if status != "OK" or not data.get("results"):
        return Place(present=False, reason="no-result")
    label = _compose(data["results"])
    if not label:
        return Place(present=False, reason="no-result")
    return Place(present=True, source="google-geocoding", label=label, lat=lat, lon=lon)
