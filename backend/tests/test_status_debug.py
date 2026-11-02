import pytest
from fastapi.testclient import TestClient

import findme.settings as settings
from findme.app.factory import create_app
from findme.store import write_counter
from findme.trace import TraceWriter
from tests.test_media import noise_jpeg


@pytest.fixture
def ctx(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    album_id = client.post("/albums", json={"photoCount": 4}).json()["albumId"]
    files = [(f"p{i}", (f"{i}.jpg", noise_jpeg(i), "image/jpeg")) for i in range(3)]
    client.post("/upload", data={"albumId": album_id}, files=files)
    return tmp_path, client, album_id


def test_status_aggregates_counters(ctx):
    root, client, album_id = ctx
    client.post(f"/albums/{album_id}/commit", json={"uploaded": 3})
    write_counter(root, album_id, "embedding", "b0", {"photosDone": 2, "facesFound": 7})
    r = client.get(f"/albums/{album_id}/status")
    body = r.json()
    assert body["stage"] == "embedding"
    assert body["photosDone"] == 2
    assert body["facesFound"] == 7
    assert body["gpsCoverage"]["total"] == 3
    assert body["stages"] == ["received", "extracting", "embedding", "ready"]


def test_status_unknown_album(ctx):
    _, client, _ = ctx
    r = client.get("/albums/00000000-0000-0000-0000-000000000000/status")
    assert r.status_code == 404


def test_debug_merged_cursor_and_snapshot(ctx):
    root, client, album_id = ctx
    w = TraceWriter(root, album_id, "find")
    w.emit("find", "search.done", matches=3)
    w.emit("external", "geocode.call", status=200)
    r = client.get(f"/debug/{album_id}")
    body = r.json()
    assert body["cursor"] == 2
    assert [e["event"] for e in body["events"]] == ["search.done", "geocode.call"]
    assert body["snapshot"]["circuits"]["google"] in ("open", "closed")
    r2 = client.get(f"/debug/{album_id}", params={"cursor": body["cursor"]})
    assert r2.json()["events"] == []


def test_debug_gated_by_env(ctx, monkeypatch):
    _, client, album_id = ctx
    monkeypatch.setattr(settings, "DEBUG_UI", False)
    r = client.get(f"/debug/{album_id}")
    assert r.status_code == 404
