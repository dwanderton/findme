"""External-call tracing: every backend upstream request lands in the album trace."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import findme.places as places_mod
import findme.routes.staticmap as staticmap_mod
import findme.weather as weather_mod
from findme.app.factory import create_app
from findme.places import AUTOCOMPLETE_URL
from findme.routes.staticmap import STATIC_URL
from findme.trace import TraceWriter, read_merged
from findme.upstream import Circuit, UpstreamDown, get_json
from findme.weather import FORECAST_URL
from tests.test_media import noise_jpeg


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    places_mod.circuit = Circuit("places")
    staticmap_mod.circuit = Circuit("staticmap")
    weather_mod.circuit = Circuit("open-meteo")
    app = create_app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    album_id = client.post("/albums", json={"photoCount": 2}).json()["albumId"]
    return tmp_path, client, album_id


def events_for(root, album_id, src=None):
    events, _ = read_merged(root, album_id)
    return [e for e in events if src is None or e["src"] == src]


@respx.mock
async def test_get_json_emits_success_with_request_id(tmp_path):
    respx.get(FORECAST_URL).respond(json={"ok": True})
    trace = TraceWriter(tmp_path, "a1", "t")
    (tmp_path / "albums" / "a1").mkdir(parents=True, exist_ok=True)
    circuit = Circuit("open-meteo")
    async with httpx.AsyncClient() as c:
        await get_json(c, circuit, FORECAST_URL, {}, trace=trace, request_id="rid-123")
    (e,) = events_for(tmp_path, "a1", "external")
    assert e["event"] == "open-meteo"
    assert e["requestId"] == "rid-123"
    assert e["data"]["status"] == 200
    assert e["data"]["host"] == "api.open-meteo.com"
    assert e["data"]["ms"] >= 0


@respx.mock
async def test_get_json_emits_retries_then_circuit_open(tmp_path):
    respx.get(FORECAST_URL).respond(status_code=500)
    trace = TraceWriter(tmp_path, "a1", "t")
    circuit = Circuit("open-meteo")

    async def no_sleep(_):
        return None

    async with httpx.AsyncClient() as c:
        with pytest.raises(UpstreamDown):
            await get_json(c, circuit, FORECAST_URL, {}, sleep=no_sleep, trace=trace)
    events = events_for(tmp_path, "a1", "external")
    attempts = [e for e in events if e["event"] == "open-meteo"]
    assert len(attempts) == 3
    assert all(e["level"] == "warn" and e["data"]["status"] == 500 for e in attempts)
    assert [e["data"]["attempt"] for e in attempts] == [0, 1, 2]
    (tripped,) = [e for e in events if e["event"] == "circuit.open"]
    assert tripped["level"] == "error"
    assert tripped["data"]["api"] == "open-meteo"


@respx.mock
def test_autocomplete_traces_google_call(ctx):
    root, client, album_id = ctx
    respx.post(AUTOCOMPLETE_URL).respond(json={"suggestions": []})
    r = client.get(
        "/places/autocomplete",
        params={"q": "shore", "session": "11111111-1111", "albumId": album_id},
        headers={"x-request-id": "rid-places"},
    )
    assert r.status_code == 200
    (e,) = events_for(root, album_id, "external")
    assert e["event"] == "places"
    assert e["requestId"] == "rid-places"
    assert e["data"]["host"] == "places.googleapis.com"
    assert e["data"]["status"] == 200


@respx.mock
def test_autocomplete_failure_traces_error(ctx):
    root, client, album_id = ctx
    respx.post(AUTOCOMPLETE_URL).respond(status_code=500)
    r = client.get(
        "/places/autocomplete",
        params={"q": "shore", "session": "11111111-1111", "albumId": album_id},
    )
    assert r.json() == {"suggestions": [], "degraded": "upstream-failed"}
    (e,) = events_for(root, album_id, "external")
    assert e["level"] == "error"
    assert e["data"]["status"] == 500
    assert places_mod.circuit.state == "open"


def test_autocomplete_bogus_album_writes_nothing(ctx, tmp_path):
    _, client, _ = ctx
    with respx.mock:
        respx.post(AUTOCOMPLETE_URL).respond(json={"suggestions": []})
        client.get(
            "/places/autocomplete",
            params={"q": "shore", "session": "11111111-1111", "albumId": "not-an-album"},
        )
    assert not (tmp_path / "albums" / "not-an-album").exists()


@respx.mock
def test_staticmap_traces_and_uses_maps_code(ctx):
    root, client, album_id = ctx
    respx.get(STATIC_URL).respond(content=b"\x89PNG", headers={"content-type": "image/png"})
    r = client.get("/staticmap", params={"lat": 1.0, "lon": 2.0, "albumId": album_id})
    assert r.status_code == 200
    (e,) = events_for(root, album_id, "external")
    assert e["event"] == "staticmap"
    assert e["data"]["status"] == 200

    respx.get(STATIC_URL).respond(status_code=403, content=b"denied", headers={"content-type": "text/plain"})
    staticmap_mod.circuit = Circuit("staticmap")
    r2 = client.get("/staticmap", params={"lat": 1.0, "lon": 2.0, "albumId": album_id})
    assert r2.status_code == 502
    assert r2.json()["error"]["code"] == "UPSTREAM_MAPS"
    errors = [e for e in events_for(root, album_id, "external") if e["level"] == "error"]
    assert errors and errors[-1]["data"]["status"] == 403
    assert staticmap_mod.circuit.state == "open"


def test_api_error_echoes_request_id_and_traces(ctx):
    root, client, album_id = ctx
    r = client.get(
        "/find",
        params={"userId": "nobody", "albumId": album_id},
        headers={"x-request-id": "rid-err"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["requestId"] == "rid-err"
    (e,) = events_for(root, album_id, "api")
    assert e["event"] == "error.INDEX_NOT_READY"
    assert e["level"] == "warn"
    assert e["requestId"] == "rid-err"
    assert e["data"]["status"] == 409


def test_debug_snapshot_lists_all_circuits(ctx):
    _, client, album_id = ctx
    snap = client.get(f"/debug/{album_id}").json()["snapshot"]
    assert set(snap["circuits"]) == {"google", "places", "open-meteo", "staticmap"}
    assert all(v in ("open", "closed") for v in snap["circuits"].values())
    assert "rateLimit" not in snap and "enrichBudget" not in snap
