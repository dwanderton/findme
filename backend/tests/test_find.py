import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

import findme.routes.enroll as enroll_route
from findme.app.factory import create_app
from findme.faces import save_refs
from findme.jobs.index_gpu import run_all_batches
from tests.test_media import noise_jpeg

PERSON = {}


def unit(v):
    v = np.asarray(v, np.float32)
    return v / np.linalg.norm(v)


class FakeEngine:
    active_provider = "CPUExecutionProvider"

    def __init__(self):
        rng = np.random.default_rng(1234)
        PERSON["me"] = unit(rng.standard_normal(512))
        PERSON["other"] = unit(rng.standard_normal(512))
        self.calls = 0

    def faces_from_bytes(self, data, retry_large=False):
        return "pil", [(np.array([0.0, 0.0, 100.0, 110.0]), 0.9, np.zeros((5, 2)))]

    def embed(self, pil, kps):
        rng = np.random.default_rng(self.calls)
        self.calls += 1
        who = PERSON["me"] if self.calls % 2 == 1 else PERSON["other"]
        return unit(0.97 * who + 0.24 * unit(rng.standard_normal(512)))


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.delenv("VLM_BASE_URL", raising=False)
    app = create_app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    album_id = client.post("/albums", json={"photoCount": 4}).json()["albumId"]
    files = [(f"p{i}", (f"{i}.jpg", noise_jpeg(i), "image/jpeg")) for i in range(4)]
    exif = {
        "exif_p0": json.dumps(
            {"gps_present": True, "lat": 37.4267, "lon": -122.0806, "taken_at": "2026-09-14T14:20:00", "make": "Sony"}
        )
    }
    client.post("/upload", data={"albumId": album_id, **exif}, files=files)
    client.post(f"/albums/{album_id}/commit", json={"uploaded": 4})
    run_all_batches(tmp_path, album_id, engine=FakeEngine())
    user_id = save_refs(tmp_path, None, PERSON["me"][None])
    return tmp_path, client, album_id, user_id


def test_find_contract_and_bands(ctx):
    _, client, album_id, user_id = ctx
    r = client.get("/find", params={"userId": user_id, "albumId": album_id, "threshold": "possible"})
    assert r.status_code == 200
    body = r.json()
    assert body["album"]["faces"] == 4
    assert len(body["matches"]) == 2
    for m in body["matches"]:
        assert m["band"] in ("strong", "possible")
        assert set(m) >= {"photoId", "score", "bbox", "camera", "place", "weather", "vlm", "enrichment"}
    assert body["vlmSummary"]["unavailable"] == 2
    assert body["story"]["status"] == "unavailable"


def test_enrichment_states_surface(ctx):
    _, client, album_id, user_id = ctx
    r = client.get("/find", params={"userId": user_id, "albumId": album_id, "threshold": "possible"})
    statuses = {m["enrichment"]["status"] for m in r.json()["matches"]}
    assert "metadata-scrubbed" in statuses or "partial" in statuses or "upstream-failed" in statuses


def test_not_ready_409(ctx, tmp_path):
    root, client, album_id, user_id = ctx
    from findme.albums import load_meta, save_meta

    meta = load_meta(root, album_id)
    meta["stage"] = "embedding"
    save_meta(root, meta)
    r = client.get("/find", params={"userId": user_id, "albumId": album_id})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INDEX_NOT_READY"


def test_unknown_user_404(ctx):
    _, client, album_id, _ = ctx
    r = client.get("/find", params={"userId": "00000000-0000-0000-0000-000000000000", "albumId": album_id})
    assert r.status_code == 404


def test_vlm_pending_kicks_runner(ctx):
    root, client, album_id, user_id = ctx
    calls = []
    client.app.state.run_vlm = lambda *a: calls.append(a)
    r = client.get("/find", params={"userId": user_id, "albumId": album_id, "threshold": "possible"})
    body = r.json()
    assert body["vlmSummary"]["pending"] == 2
    assert body["story"]["status"] == "pending"
    assert len(calls) == 1
