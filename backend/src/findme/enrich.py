from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import httpx

from findme.clusters import ClusterCache
from findme.geo import reverse_geocode
from findme.schemas import ExifData, Place, Weather, clean
from findme.weather import weather_at

MAX_UNCACHED_PER_FIND = 50


@dataclass
class Enriched:
    place: Place
    weather: Weather
    status: str


def _status(e: ExifData, venue: dict | None, place: Place, weather: Weather) -> str:
    has_location = e.gps_present or venue is not None
    if not has_location:
        return "metadata-scrubbed"
    if place.present and weather.present:
        return "full"
    if not place.present and not weather.present:
        if place.reason == "upstream-failed" and weather.reason in ("upstream-failed", "no-timestamp"):
            return "upstream-failed"
        if place.reason == "deferred":
            return "deferred"
    return "partial"


class Enricher:
    def __init__(self, root: Path, album_id: str, venue: dict | None = None):
        self.cache = ClusterCache(root, album_id)
        self.venue = venue
        self.uncached_used = 0

    async def enrich(self, client: httpx.AsyncClient, exif: ExifData) -> Enriched:
        venue = self.venue
        if exif.gps_present:
            lat, lon, place_known = exif.lat, exif.lon, None
        elif venue:
            lat, lon = venue["lat"], venue["lon"]
            place_known = Place(
                present=True, source="user-venue", label=venue["label"], lat=lat, lon=lon
            )
        else:
            return Enriched(
                place=Place(present=False, reason="no-gps"),
                weather=Weather(present=False, reason="no-gps"),
                status="metadata-scrubbed",
            )

        cached_place, cached_weather = self.cache.lookup(lat, lon, exif.taken_at)
        place = place_known or (Place(**cached_place) if cached_place else None)
        weather = Weather(**cached_weather) if cached_weather else None

        need_place = place is None
        need_weather = weather is None and exif.taken_at is not None

        if (need_place or need_weather) and self.uncached_used >= MAX_UNCACHED_PER_FIND:
            place = place or Place(present=False, reason="deferred")
            weather = weather or Weather(present=False, reason="deferred")
            return Enriched(place=place, weather=weather, status="deferred")

        tasks = {}
        if need_place:
            tasks["place"] = reverse_geocode(client, lat, lon)
        if need_weather:
            basis = "photo-gps" if exif.gps_present else "venue-location"
            tasks["weather"] = weather_at(client, lat, lon, exif.taken_at, basis=basis)
        if tasks:
            self.uncached_used += 1
            results = await asyncio.gather(*tasks.values())
            got = dict(zip(tasks.keys(), results))
            if need_place:
                place = got["place"]
            if need_weather:
                weather = got["weather"]
            self.cache.store(
                lat,
                lon,
                exif.taken_at,
                clean(place) if place and place.present else None,
                clean(weather) if weather and weather.present else None,
            )

        if weather is None:
            weather = Weather(present=False, reason="no-timestamp")
        if place is None:
            place = Place(present=False, reason="no-result")

        return Enriched(place=place, weather=weather, status=_status(exif, venue, place, weather))
