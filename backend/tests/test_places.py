import pytest
import respx
from fastapi.testclient import TestClient

import findme.places as places_mod
from findme.app.factory import create_app
from findme.places import AUTOCOMPLETE_URL, DETAILS_URL
from findme.upstream import Circuit


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    places_mod.circuit = Circuit("places")
    return TestClient(create_app(tmp_path), raise_server_exceptions=False)


@respx.mock
def test_autocomplete_new_api_shape(client):
    route = respx.post(AUTOCOMPLETE_URL).respond(
        json={
            "suggestions": [
                {
                    "placePrediction": {
                        "placeId": "pid1",
                        "text": {"text": "Shoreline Amphitheatre, Mountain View, CA"},
                    }
                }
            ]
        }
    )
    r = client.get("/places/autocomplete", params={"q": "shore", "session": "11111111-1111"})
    assert r.status_code == 200
    assert r.json()["suggestions"][0] == {
        "placeId": "pid1",
        "label": "Shoreline Amphitheatre, Mountain View, CA",
    }
    req = route.calls[0].request
    assert req.headers["x-goog-api-key"] == "test-key"
    assert b"sessionToken" in req.content


@respx.mock
def test_autocomplete_degraded_on_failure(client):
    respx.post(AUTOCOMPLETE_URL).respond(status_code=500)
    r = client.get("/places/autocomplete", params={"q": "shore", "session": "11111111-1111"})
    assert r.status_code == 200
    assert r.json() == {"suggestions": [], "degraded": "upstream-failed"}
    assert places_mod.circuit.state == "open"


@respx.mock
async def test_details_new_api(client, monkeypatch):
    import httpx

    places_mod.circuit = Circuit("places")
    route = respx.get(f"{DETAILS_URL}/pid1").respond(
        json={
            "id": "pid1",
            "displayName": {"text": "Shoreline Amphitheatre"},
            "formattedAddress": "1 Amphitheatre Pkwy, Mountain View, CA",
            "location": {"latitude": 37.4267, "longitude": -122.0806},
        }
    )
    from findme.places import details

    async with httpx.AsyncClient() as c:
        v = await details(c, "pid1", "sess")
    assert v == {
        "placeId": "pid1",
        "label": "Shoreline Amphitheatre",
        "lat": 37.4267,
        "lon": -122.0806,
    }
    assert "location" in route.calls[0].request.headers["x-goog-fieldmask"]


def test_query_validation(client):
    assert client.get("/places/autocomplete", params={"q": "ab", "session": "11111111-1111"}).status_code == 422
    assert client.get("/places/autocomplete", params={"q": "abcd"}).status_code == 422
