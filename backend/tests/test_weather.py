from datetime import date

import httpx
import pytest
import respx

import findme.weather as weather
from findme.upstream import Circuit
from findme.weather import ARCHIVE_URL, FORECAST_URL, weather_at

LAT, LON = 37.4267, -122.0806
TODAY = date(2026, 11, 2)


def hourly_body(times, temps, codes):
    n = len(times)
    return {
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "weathercode": codes,
            "cloud_cover": [5] * n,
            "wind_speed_10m": [11.2] * n,
        }
    }


@pytest.fixture(autouse=True)
def fresh_circuit():
    weather.circuit = Circuit("open-meteo")


@respx.mock
async def test_old_date_uses_archive_nearest_hour():
    respx.get(ARCHIVE_URL).respond(
        json=hourly_body(
            ["2026-09-14T14:00", "2026-09-14T15:00"], [18.4, 19.1], [0, 1]
        )
    )
    async with httpx.AsyncClient() as c:
        w = await weather_at(c, LAT, LON, "2026-09-14T14:20:11-07:00", today=TODAY)
    assert w.present and w.source == "open-meteo"
    assert w.tempC == 18.4
    assert w.condition == "clear sky"
    assert w.localTime == "14:20"


@respx.mock
async def test_recent_date_switches_to_forecast():
    respx.get(FORECAST_URL).respond(
        json=hourly_body(["2026-11-01T09:00"], [12.0], [61])
    )
    async with httpx.AsyncClient() as c:
        w = await weather_at(c, LAT, LON, "2026-11-01T09:10:00-07:00", today=TODAY)
    assert w.present and w.condition == "light rain"
    assert respx.calls[0].request.url.host == "api.open-meteo.com"


@respx.mock
async def test_boundary_day_7_back_uses_archive():
    respx.get(ARCHIVE_URL).respond(json=hourly_body(["2026-10-26T10:00"], [15.0], [2]))
    async with httpx.AsyncClient() as c:
        w = await weather_at(c, LAT, LON, "2026-10-26T10:00:00", today=TODAY)
    assert w.present
    assert respx.calls[0].request.url.host == "archive-api.open-meteo.com"


@respx.mock
async def test_null_rows_reported_no_data():
    respx.get(ARCHIVE_URL).respond(
        json=hourly_body(["2026-09-14T14:00"], [None], [None])
    )
    async with httpx.AsyncClient() as c:
        w = await weather_at(c, LAT, LON, "2026-09-14T14:32:00", today=TODAY)
    assert not w.present and w.reason == "no-data"


async def test_no_timestamp():
    async with httpx.AsyncClient() as c:
        w = await weather_at(c, LAT, LON, "", today=TODAY)
    assert not w.present and w.reason == "no-timestamp"


@respx.mock
async def test_circuit_independent_from_geo(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("findme.upstream.asyncio.sleep", no_sleep)
    respx.get(ARCHIVE_URL).respond(status_code=500)
    import findme.geo as geo

    async with httpx.AsyncClient() as c:
        w = await weather_at(c, LAT, LON, "2026-09-14T14:00:00", today=TODAY)
    assert w.reason == "upstream-failed"
    assert weather.circuit.state == "open"
    assert geo.circuit.state == "closed"
