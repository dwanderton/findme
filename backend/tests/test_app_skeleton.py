from fastapi.testclient import TestClient

from findme.app.factory import create_app


def test_app_builds_and_health(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_api_error_envelope_wiring(tmp_path):
    from fastapi import APIRouter

    from findme.errors import ApiError

    app = create_app(tmp_path)
    router = APIRouter()

    @router.get("/boom")
    async def boom():
        raise ApiError("UNKNOWN_ALBUM", "nope")

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "UNKNOWN_ALBUM"


def test_settings_match_architecture():
    from findme import settings

    assert settings.BATCH_SIZE == 50
    assert settings.MAX_PHOTOS == 5000
