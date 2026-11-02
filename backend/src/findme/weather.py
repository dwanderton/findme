from __future__ import annotations

from datetime import date, datetime, timedelta

import httpx

from findme.schemas import Weather
from findme.upstream import Circuit, UpstreamDown, get_json

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_LAG_DAYS = 6
HOURLY = "temperature_2m,weathercode,cloud_cover,wind_speed_10m"

WMO = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "dense drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "heavy freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "violent showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}

circuit = Circuit("open-meteo")


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


async def weather_at(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    taken_at: str,
    basis: str = "photo-gps",
    today: date | None = None,
) -> Weather:
    dt = _parse(taken_at)
    if dt is None:
        return Weather(present=False, reason="no-timestamp")
    day = dt.date()
    today = today or date.today()
    recent = (today - day) <= timedelta(days=ARCHIVE_LAG_DAYS)
    if recent:
        past_days = max((today - day).days + 1, 1)
        url, params = FORECAST_URL, {
            "latitude": lat,
            "longitude": lon,
            "past_days": min(past_days, 92),
            "hourly": HOURLY,
            "timezone": "auto",
        }
    else:
        url, params = ARCHIVE_URL, {
            "latitude": lat,
            "longitude": lon,
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "hourly": HOURLY,
            "timezone": "auto",
        }
    try:
        data = await get_json(client, circuit, url, params)
    except UpstreamDown:
        return Weather(present=False, reason="upstream-failed")

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    codes = hourly.get("weathercode") or []
    clouds = hourly.get("cloud_cover") or []
    winds = hourly.get("wind_speed_10m") or []
    if not times:
        return Weather(present=False, reason="no-data")

    local = dt.replace(tzinfo=None)
    best_i, best_gap = None, None
    for i, t in enumerate(times):
        row = _parse(t)
        if row is None:
            continue
        gap = abs((row - local).total_seconds())
        if best_gap is None or gap < best_gap:
            best_i, best_gap = i, gap
    if best_i is None or temps[best_i] is None:
        return Weather(present=False, reason="no-data")

    code = codes[best_i] if best_i < len(codes) else None
    return Weather(
        present=True,
        source="open-meteo",
        basis=basis,
        tempC=round(float(temps[best_i]), 1),
        condition=WMO.get(int(code), "unknown") if code is not None else "unknown",
        cloudCoverPct=float(clouds[best_i]) if best_i < len(clouds) and clouds[best_i] is not None else None,
        windKmh=float(winds[best_i]) if best_i < len(winds) and winds[best_i] is not None else None,
        localTime=local.strftime("%H:%M"),
    )
