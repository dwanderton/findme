from findme.clusters import ClusterCache, haversine_m

BASE = (37.4267, -122.0806)
TS = "2026-09-14T14:32:00-07:00"
PLACE = {"label": "Shoreline Amphitheatre", "source": "google-geocoding"}
WX = {"tempC": 18.4, "condition": "clear sky"}


def offset_m(meters: float) -> tuple[float, float]:
    return BASE[0] + meters / 111_132.0, BASE[1]


def test_haversine_sanity():
    lat2, lon2 = offset_m(402)
    assert abs(haversine_m(*BASE, lat2, lon2) - 402) < 2


def test_place_hit_at_400m_miss_at_405m(tmp_path):
    c = ClusterCache(tmp_path, "a1")
    c.store(*BASE, TS, PLACE, WX)
    p, _ = c.lookup(*offset_m(400), TS)
    assert p == PLACE
    p, _ = c.lookup(*offset_m(405), TS)
    assert p is None


def test_place_ignores_time(tmp_path):
    c = ClusterCache(tmp_path, "a1")
    c.store(*BASE, TS, PLACE, None)
    p, _ = c.lookup(*BASE, "2026-09-16T09:00:00-07:00")
    assert p == PLACE


def test_weather_window_29_vs_31_min(tmp_path):
    c = ClusterCache(tmp_path, "a1")
    c.store(*BASE, TS, None, WX)
    _, w = c.lookup(*BASE, "2026-09-14T15:01:00-07:00")
    assert w == WX
    _, w = c.lookup(*BASE, "2026-09-14T15:03:00-07:00")
    assert w is None


def test_weather_radius_1600_vs_1620(tmp_path):
    c = ClusterCache(tmp_path, "a1")
    c.store(*BASE, TS, None, WX)
    _, w = c.lookup(*offset_m(1600), TS)
    assert w == WX
    _, w = c.lookup(*offset_m(1620), TS)
    assert w is None


def test_partial_entry_merge(tmp_path):
    c = ClusterCache(tmp_path, "a1")
    c.store(*BASE, TS, PLACE, None)
    p, w = c.lookup(*BASE, TS)
    assert p == PLACE and w is None
    c.store(*BASE, TS, None, WX)
    p, w = c.lookup(*BASE, TS)
    assert p == PLACE and w == WX


def test_no_timestamp_no_weather(tmp_path):
    c = ClusterCache(tmp_path, "a1")
    c.store(*BASE, TS, PLACE, WX)
    p, w = c.lookup(*BASE, None)
    assert p == PLACE and w is None
