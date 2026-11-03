import pytest
import respx
from fastapi.testclient import TestClient

import findme.routes.staticmap as staticmap_mod
from findme.app.factory import create_app
from findme.routes.staticmap import STATIC_URL
from findme.upstream import Circuit


@pytest.fixture(autouse=True)
def fresh_circuit():
    staticmap_mod.circuit = Circuit("staticmap")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    return TestClient(create_app(tmp_path), raise_server_exceptions=False)


@respx.mock
def test_proxies_png_and_hides_key(client):
    route = respx.get(STATIC_URL).respond(content=b"\x89PNG\r\n\x1a\nfake", headers={"content-type": "image/png"})
    r = client.get("/staticmap", params={"lat": 37.4267, "lon": -122.0806})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content.startswith(b"\x89PNG")
    req_url = str(route.calls[0].request.url)
    assert "key=test-key" in req_url
    assert "0x5D29F0" in req_url


@respx.mock
def test_upstream_failure(client):
    respx.get(STATIC_URL).respond(status_code=403, content=b"denied", headers={"content-type": "text/plain"})
    r = client.get("/staticmap", params={"lat": 1.0, "lon": 2.0})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "UPSTREAM_MAPS"
    assert staticmap_mod.circuit.state == "open"


def test_circuit_open_short_circuits(client):
    staticmap_mod.circuit.trip()
    r = client.get("/staticmap", params={"lat": 1.0, "lon": 2.0})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "UPSTREAM_MAPS"


def test_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    c = TestClient(create_app(tmp_path), raise_server_exceptions=False)
    assert c.get("/staticmap", params={"lat": 1.0, "lon": 2.0}).status_code == 502


def test_zoom_bounds(client):
    assert client.get("/staticmap", params={"lat": 1, "lon": 2, "zoom": 0}).status_code == 422
    assert client.get("/staticmap", params={"lat": 1, "lon": 2, "zoom": 21}).status_code == 422
