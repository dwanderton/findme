import pytest
import respx
from fastapi.testclient import TestClient

import findme.places as places_mod
from findme.app.factory import create_app
from findme.places import AUTOCOMPLETE_URL
from findme.upstream import Circuit


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    places_mod.circuit = Circuit("places")
    return TestClient(create_app(tmp_path), raise_server_exceptions=False)


@respx.mock
def test_autocomplete_shape(client):
    respx.get(AUTOCOMPLETE_URL).respond(
        json={
            "status": "OK",
            "predictions": [
                {"place_id": "pid1", "description": "Shoreline Amphitheatre, Mountain View"},
            ],
        }
    )
    r = client.get("/places/autocomplete", params={"q": "shore", "session": "11111111-1111"})
    assert r.status_code == 200
    assert r.json()["suggestions"][0] == {"placeId": "pid1", "label": "Shoreline Amphitheatre, Mountain View"}


@respx.mock
def test_autocomplete_degraded_on_failure(client, monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("findme.upstream.asyncio.sleep", no_sleep)
    respx.get(AUTOCOMPLETE_URL).respond(status_code=500)
    r = client.get("/places/autocomplete", params={"q": "shore", "session": "11111111-1111"})
    assert r.status_code == 200
    assert r.json() == {"suggestions": [], "degraded": "upstream-failed"}


def test_query_validation(client):
    assert client.get("/places/autocomplete", params={"q": "ab", "session": "11111111-1111"}).status_code == 422
    assert client.get("/places/autocomplete", params={"q": "abcd"}).status_code == 422
