from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

PLACE_RADIUS_M = 402
WEATHER_RADIUS_M = 1609
WEATHER_WINDOW_MIN = 30


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _minutes_apart(a: str | None, b: str | None) -> float | None:
    da, db = _parse_ts(a), _parse_ts(b)
    if da is None or db is None:
        return None
    if (da.tzinfo is None) != (db.tzinfo is None):
        da, db = da.replace(tzinfo=None), db.replace(tzinfo=None)
    return abs((da - db).total_seconds()) / 60


class ClusterCache:
    def __init__(self, root: Path, album_id: str):
        self.dir = root / "enrich" / album_id / "clusters"
        self.dir.mkdir(parents=True, exist_ok=True)

    def entries(self) -> list[dict]:
        out = []
        for f in sorted(self.dir.glob("*.json")):
            try:
                out.append(json.loads(f.read_text()))
            except Exception:
                continue
        return out

    def lookup(self, lat: float, lon: float, ts: str | None) -> tuple[dict | None, dict | None]:
        place, weather = None, None
        for e in self.entries():
            d = haversine_m(lat, lon, e["lat"], e["lon"])
            if place is None and d <= PLACE_RADIUS_M and e.get("place"):
                place = e["place"]
            if weather is None and d <= WEATHER_RADIUS_M and e.get("weather"):
                mins = _minutes_apart(ts, e.get("ts"))
                if mins is not None and mins <= WEATHER_WINDOW_MIN:
                    weather = e["weather"]
            if place and weather:
                break
        return place, weather

    def store(self, lat: float, lon: float, ts: str | None, place: dict | None, weather: dict | None) -> None:
        key = hashlib.sha256(f"{lat:.6f},{lon:.6f},{ts}".encode()).hexdigest()[:16]
        path = self.dir / f"{key}.json"
        if path.exists():
            merged = json.loads(path.read_text())
            merged["place"] = merged.get("place") or place
            merged["weather"] = merged.get("weather") or weather
        else:
            merged = {"lat": lat, "lon": lon, "ts": ts, "place": place, "weather": weather}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(merged))
        tmp.replace(path)
