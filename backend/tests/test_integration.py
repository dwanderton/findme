import json

import pytest
import respx
from fastapi.testclient import TestClient

import findme.geo as geo
import findme.weather as weather_mod
from findme.app.factory import create_app
from findme.engine import models_dir
from findme.geo import GEOCODE_URL
from findme.jobs.index_gpu import run_all_batches
from findme.upstream import Circuit
from findme.weather import ARCHIVE_URL
from tests.fixtures import corrupt_jpeg, jpeg_with_exif
from tests.test_media import gradient_jpeg, noise_jpeg

MODELS = models_dir()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (MODELS / "det_10g.onnx").exists(), reason="reference models not staged"),
]

GEO_OK = {"status": "OK", "results": [{"types": ["point_of_interest"], "formatted_address": "Shoreline Amphitheatre"}]}
WX_OK = {
    "hourly": {
        "time": ["2026-09-14T14:00"],
        "temperature_2m": [18.4],
        "weathercode": [0],
        "cloud_cover": [5],
        "wind_speed_10m": [11.2],
    }
}


@pytest.fixture(scope="module")
def flow(tmp_path_factory):
    root = tmp_path_factory.mktemp("storage")
    app = create_app(root)
    client = TestClient(app, raise_server_exceptions=False)

    album = client.post("/albums", json={"photoCount": 12}).json()
    album_id, owner = album["albumId"], album["ownerToken"]

    crowd_a = (MODELS / "s2_a.jpg").read_bytes()
    crowd_b = (MODELS / "s2_b.jpg").read_bytes()
    gps_exif = json.dumps({"gps_present": True, "lat": 37.4267, "lon": -122.0806, "taken_at": "2026-09-14T14:20:00", "make": "Sony", "model": "ILCE-7M4"})
    files = [
        ("p0", ("crowd_a.jpg", crowd_a, "image/jpeg")),
        ("p1", ("crowd_b.jpg", crowd_b, "image/jpeg")),
        ("p2", ("noface.jpg", gradient_jpeg(640, 480), "image/jpeg")),
        ("p3", ("scrubbed.jpg", noise_jpeg(3), "image/jpeg")),
        ("p4", ("broken.jpg", corrupt_jpeg(), "image/jpeg")),
        ("p5", ("gpsnoface.jpg", jpeg_with_exif(), "image/jpeg")),
    ]
    r = client.post("/upload", data={"albumId": album_id, "exif_p0": gps_exif}, files=files)
    assert r.json()["stored"] == 6
    commit = client.post(f"/albums/{album_id}/commit", json={"uploaded": 6}).json()
    run_all_batches(root, album_id)

    data = (MODELS / "s2_a.jpg").read_bytes()
    enroll = client.post("/enroll", files=[("s0", ("me.jpg", data, "image/jpeg"))]).json()
    return root, client, album_id, owner, enroll["userId"], commit


def test_commit_handles_messy_album(flow):
    *_, commit = flow
    assert commit["accepted"] == 5
    assert any(x["reason"] == "undecodable" for x in commit["rejected"])


def test_status_ready_with_gps_coverage(flow):
    _, client, album_id, *_ = flow
    s = client.get(f"/albums/{album_id}/status").json()
    assert s["stage"] == "ready"
    assert s["facesFound"] > 40
    assert s["gpsCoverage"]["withGps"] >= 2


@respx.mock
def test_find_full_contract_on_real_pipeline(flow, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.delenv("VLM_BASE_URL", raising=False)
    geo.circuit = Circuit("google")
    weather_mod.circuit = Circuit("open-meteo")
    respx.get(GEOCODE_URL).respond(json=GEO_OK)
    respx.get(ARCHIVE_URL).respond(json=WX_OK)

    root, client, album_id, _, user_id, _ = flow
    r = client.get("/find", params={"userId": user_id, "albumId": album_id, "threshold": "possible"})
    assert r.status_code == 200
    body = r.json()

    assert body["matches"], "self-enrolled crowd selfie must match its own photo"
    photo_names = []
    from findme.albums import load_meta

    meta = load_meta(root, album_id)
    for m in body["matches"]:
        photo_names.append(meta["photos"][m["photoId"]]["name"])
        assert m["band"] in ("strong", "possible")
        assert m["enrichment"]["status"] in ("full", "partial", "metadata-scrubbed", "upstream-failed", "deferred")
        assert m["vlm"]["status"] == "unavailable"
    assert "crowd_a.jpg" in photo_names

    enriched = [m for m in body["matches"] if m["enrichment"]["status"] == "full"]
    if enriched:
        assert enriched[0]["place"]["label"] == "Shoreline Amphitheatre"
        assert enriched[0]["weather"]["tempC"] == 18.4
        assert enriched[0]["camera"]["make"] == "Sony"

    assert body["story"]["status"] == "unavailable"
    assert set(body["enrichmentSummary"]) == {"full", "partial", "scrubbed", "upstreamFailed"}


def test_download_after_find(flow):
    _, client, album_id, _, user_id, _ = flow
    r = client.get(f"/albums/{album_id}/download", params={"userId": user_id})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"


def test_second_user_shares_album(flow):
    root, client, album_id, *_ = flow
    data = (MODELS / "s2_b.jpg").read_bytes()
    enroll = client.post("/enroll", files=[("s0", ("me2.jpg", data, "image/jpeg"))]).json()
    r = client.get("/find", params={"userId": enroll["userId"], "albumId": album_id, "threshold": "possible"})
    assert r.status_code == 200


def test_delete_erases_everything(flow):
    root, client, album_id, owner, user_id, _ = flow
    assert client.delete(f"/albums/{album_id}", headers={"X-Owner-Token": owner}).status_code == 204
    assert client.delete(f"/users/{user_id}").status_code == 204
    assert client.get(f"/albums/{album_id}/status").status_code == 404
    assert not (root / "albums" / album_id).exists()
