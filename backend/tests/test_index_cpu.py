import json

import pytest
from fastapi.testclient import TestClient

from findme.albums import load_meta
from findme.app.factory import create_app
from tests.fixtures import corrupt_jpeg, jpeg_with_exif
from tests.test_media import gradient_jpeg, noise_jpeg


@pytest.fixture
def ctx(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    album_id = client.post("/albums", json={"photoCount": 12}).json()["albumId"]
    return tmp_path, client, album_id


def upload(client, album_id, parts, exif=None):
    data = {"albumId": album_id}
    if exif:
        data.update(exif)
    return client.post("/upload", data=data, files=parts)


def test_create_album_contract(ctx):
    _, client, _ = ctx
    r = client.post("/albums", json={"photoCount": 50})
    body = r.json()
    assert r.status_code == 201
    assert body["upload"]["batchMaxPhotos"] == 8
    assert len(body["ownerToken"]) == 36


def test_commit_pipeline_dedupe_exif_thumbs_batches(ctx):
    root, client, album_id = ctx
    client_exif = json.dumps({"gps_present": True, "lat": 37.4, "lon": -122.1, "taken_at": "2026-09-14T14:20:00"})
    parts = [
        ("p0", ("gps.jpg", jpeg_with_exif(), "image/jpeg")),
        ("p1", ("dupe1.jpg", gradient_jpeg(), "image/jpeg")),
        ("p2", ("dupe2.jpg", gradient_jpeg(shift=1), "image/jpeg")),
        ("p3", ("noise.jpg", noise_jpeg(5), "image/jpeg")),
        ("p4", ("broken.jpg", corrupt_jpeg(), "image/jpeg")),
    ]
    assert upload(client, album_id, parts, exif={"exif_p3": client_exif}).json()["stored"] == 5
    r = client.post(f"/albums/{album_id}/commit", json={"uploaded": 5})
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 3
    reasons = sorted(x["reason"] for x in body["rejected"])
    assert reasons == ["duplicate", "undecodable"]
    by_reason = {x["reason"]: x["name"] for x in body["rejected"]}
    assert by_reason["undecodable"] == "broken.jpg"
    assert by_reason["duplicate"] in ("dupe1.jpg", "dupe2.jpg")

    meta = load_meta(root, album_id)
    assert meta["stage"] == "embedding"
    assert len(meta["batches"]) == 1
    exifs = {p["name"]: p.get("exif", {}) for p in meta["photos"].values()}
    assert exifs["gps.jpg"]["gps_present"] is True
    assert exifs["gps.jpg"]["make"] == "Sony"
    assert exifs["noise.jpg"]["gps_present"] is True
    assert exifs["noise.jpg"]["lat"] == 37.4
    thumbs = list((root / "albums" / album_id / "thumbs").glob("*.webp"))
    assert len(thumbs) == 3


def test_gps_coverage(ctx):
    root, client, album_id = ctx
    parts = [("p0", ("a.jpg", jpeg_with_exif(), "image/jpeg")), ("p1", ("b.jpg", noise_jpeg(9), "image/jpeg"))]
    upload(client, album_id, parts)
    client.post(f"/albums/{album_id}/commit", json={"uploaded": 2})
    from findme.albums import gps_coverage

    cov = gps_coverage(load_meta(root, album_id))
    assert cov == {"withGps": 1, "total": 2}
