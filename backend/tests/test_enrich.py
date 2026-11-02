import httpx
import pytest
import respx

import findme.enrich as enrich_mod
import findme.geo as geo
import findme.weather as weather_mod
from findme.enrich import Enricher
from findme.geo import GEOCODE_URL
from findme.schemas import ExifData
from findme.upstream import Circuit
from findme.weather import ARCHIVE_URL

LAT, LON = 37.4267, -122.0806
TS = "2026-09-14T14:20:00-07:00"

GEO_OK = {
    "status": "OK",
    "results": [{"types": ["point_of_interest"], "formatted_address": "Shoreline Amphitheatre"}],
}
WX_OK = {
    "hourly": {
        "time": ["2026-09-14T14:00"],
        "temperature_2m": [18.4],
        "weathercode": [0],
        "cloud_cover": [5],
        "wind_speed_10m": [11.2],
    }
}
VENUE = {"label": "Shoreline Amphitheatre", "lat": LAT, "lon": LON, "source": "user"}


def exif(gps=True, ts=TS):
    return ExifData(
        exif_present=True, gps_present=gps, lat=LAT if gps else None, lon=LON if gps else None, taken_at=ts
    )


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    geo.circuit = Circuit("google")
    weather_mod.circuit = Circuit("open-meteo")

    async def no_sleep(_):
        return None

    monkeypatch.setattr("findme.upstream.asyncio.sleep", no_sleep)


@respx.mock
async def test_full_enrichment_and_cluster_cache(tmp_path):
    g = respx.get(GEOCODE_URL).respond(json=GEO_OK)
    w = respx.get(ARCHIVE_URL).respond(json=WX_OK)
    e = Enricher(tmp_path, "a1")
    async with httpx.AsyncClient() as c:
        r1 = await e.enrich(c, exif())
        r2 = await e.enrich(c, exif(ts="2026-09-14T14:25:00-07:00"))
    assert r1.status == "full" and r1.place.label == "Shoreline Amphitheatre"
    assert r1.weather.tempC == 18.4
    assert r2.status == "full"
    assert g.call_count == 1 and w.call_count == 1


@respx.mock
async def test_one_api_down_partial_cached(tmp_path):
    respx.get(GEOCODE_URL).respond(status_code=500)
    respx.get(ARCHIVE_URL).respond(json=WX_OK)
    e = Enricher(tmp_path, "a1")
    async with httpx.AsyncClient() as c:
        r = await e.enrich(c, exif())
    assert r.status == "partial"
    assert not r.place.present and r.place.reason == "upstream-failed"
    assert r.weather.present


@respx.mock
async def test_both_down_upstream_failed(tmp_path):
    respx.get(GEOCODE_URL).respond(status_code=500)
    respx.get(ARCHIVE_URL).respond(status_code=500)
    e = Enricher(tmp_path, "a1")
    async with httpx.AsyncClient() as c:
        r = await e.enrich(c, exif())
    assert r.status == "upstream-failed"


async def test_no_gps_no_venue_scrubbed(tmp_path):
    e = Enricher(tmp_path, "a1")
    async with httpx.AsyncClient() as c:
        r = await e.enrich(c, exif(gps=False))
    assert r.status == "metadata-scrubbed"
    assert r.place.reason == "no-gps"


@respx.mock
async def test_venue_fallback_no_geocode_call(tmp_path):
    g = respx.get(GEOCODE_URL).respond(json=GEO_OK)
    respx.get(ARCHIVE_URL).respond(json=WX_OK)
    e = Enricher(tmp_path, "a1", venue=VENUE)
    async with httpx.AsyncClient() as c:
        r = await e.enrich(c, exif(gps=False))
    assert r.place.source == "user-venue"
    assert r.weather.basis == "venue-location"
    assert g.call_count == 0


async def test_venue_no_timestamp_no_weather(tmp_path):
    e = Enricher(tmp_path, "a1", venue=VENUE)
    async with httpx.AsyncClient() as c:
        r = await e.enrich(c, exif(gps=False, ts=None))
    assert r.place.source == "user-venue"
    assert not r.weather.present and r.weather.reason == "no-timestamp"
    assert r.status == "partial"


@respx.mock
async def test_budget_defers_beyond_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(enrich_mod, "MAX_UNCACHED_PER_FIND", 2)
    respx.get(GEOCODE_URL).respond(json=GEO_OK)
    respx.get(ARCHIVE_URL).respond(json=WX_OK)
    e = Enricher(tmp_path, "a1")
    async with httpx.AsyncClient() as c:
        spots = [(LAT + i * 0.1, TS) for i in range(3)]
        results = []
        for la, ts in spots:
            x = exif()
            x.lat = la
            results.append(await e.enrich(c, x))
    assert [r.status for r in results] == ["full", "full", "deferred"]
