import httpx
import pytest
import respx

import findme.geo as geo
from findme.geo import GEOCODE_URL, reverse_geocode
from findme.upstream import Circuit

LAT, LON = 37.4267, -122.0806

OK_BODY = {
    "status": "OK",
    "results": [
        {"types": ["locality"], "formatted_address": "Mountain View, CA"},
        {"types": ["point_of_interest"], "formatted_address": "Shoreline Amphitheatre, Mountain View, CA"},
    ],
}


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    geo.circuit = Circuit("google")


async def no_sleep(_):
    return None


@respx.mock
async def test_poi_preferred_over_locality():
    respx.get(GEOCODE_URL).respond(json=OK_BODY)
    async with httpx.AsyncClient() as c:
        p = await reverse_geocode(c, LAT, LON)
    assert p.present and p.source == "google-geocoding"
    assert "Shoreline" in p.label


@respx.mock
async def test_no_key_short_circuits(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY")
    async with httpx.AsyncClient() as c:
        p = await reverse_geocode(c, LAT, LON)
    assert not p.present and p.reason == "no-api-key"
    assert respx.calls.call_count == 0


@respx.mock
async def test_429_chain_opens_circuit(monkeypatch):
    monkeypatch.setattr("findme.upstream.asyncio.sleep", no_sleep)
    respx.get(GEOCODE_URL).respond(status_code=429)
    async with httpx.AsyncClient() as c:
        p = await reverse_geocode(c, LAT, LON)
        assert not p.present and p.reason == "upstream-failed"
        assert geo.circuit.state == "open"
        calls_before = respx.calls.call_count
        p2 = await reverse_geocode(c, LAT, LON)
    assert p2.reason == "upstream-failed"
    assert respx.calls.call_count == calls_before


@respx.mock
async def test_over_query_limit_trips_circuit():
    respx.get(GEOCODE_URL).respond(json={"status": "OVER_QUERY_LIMIT", "results": []})
    async with httpx.AsyncClient() as c:
        p = await reverse_geocode(c, LAT, LON)
    assert p.reason == "rate-limited"
    assert geo.circuit.state == "open"


@respx.mock
async def test_zero_results():
    respx.get(GEOCODE_URL).respond(json={"status": "ZERO_RESULTS", "results": []})
    async with httpx.AsyncClient() as c:
        p = await reverse_geocode(c, LAT, LON)
    assert not p.present and p.reason == "no-result"


@respx.mock
async def test_timeout_then_success(monkeypatch):
    monkeypatch.setattr("findme.upstream.asyncio.sleep", no_sleep)
    route = respx.get(GEOCODE_URL)
    route.side_effect = [httpx.ConnectTimeout("slow"), httpx.Response(200, json=OK_BODY)]
    async with httpx.AsyncClient() as c:
        p = await reverse_geocode(c, LAT, LON)
    assert p.present
