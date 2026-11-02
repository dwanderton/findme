import json

import pytest
from fastapi.testclient import TestClient

from findme.albums import create_album, load_meta
from findme.app.factory import create_app
from tests.fixtures import jpeg


@pytest.fixture
def ctx(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    meta = create_album(tmp_path, 100)
    return tmp_path, client, meta


def test_batch_upload_stores_and_pairs_exif(ctx):
    root, client, meta = ctx
    exif = json.dumps({"gps_present": True, "lat": 37.4, "lon": -122.0})
    r = client.post(
        "/upload",
        data={"albumId": meta["albumId"], "exif_p0": exif},
        files=[("p0", ("a.jpg", jpeg(), "image/jpeg")), ("p1", ("b.jpg", jpeg(), "image/jpeg"))],
    )
    assert r.status_code == 200
    assert r.json() == {"stored": 2, "rejected": []}
    m = load_meta(root, meta["albumId"])
    assert len(m["photos"]) == 2
    with_exif = [p for p in m["photos"].values() if p["clientExif"]]
    assert len(with_exif) == 1 and with_exif[0]["clientExif"]["lat"] == 37.4
    photo_files = list((root / "albums" / meta["albumId"] / "photos").glob("*.jpg"))
    assert len(photo_files) == 2


def test_lying_mime_rejected_batch_survives(ctx):
    _, client, meta = ctx
    r = client.post(
        "/upload",
        data={"albumId": meta["albumId"]},
        files=[("p0", ("x.jpg", b"GIF89a" + b"\x00" * 32, "image/jpeg")), ("p1", ("ok.jpg", jpeg(), "image/jpeg"))],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["stored"] == 1
    assert body["rejected"] == [{"name": "x.jpg", "reason": "UNSUPPORTED_MEDIA"}]


def test_unknown_album_404(ctx):
    _, client, _ = ctx
    r = client.post(
        "/upload",
        data={"albumId": "00000000-0000-0000-0000-000000000000"},
        files=[("p0", ("a.jpg", jpeg(), "image/jpeg"))],
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "UNKNOWN_ALBUM"


def test_batch_photo_cap(ctx):
    _, client, meta = ctx
    files = [(f"p{i}", (f"{i}.jpg", jpeg(), "image/jpeg")) for i in range(9)]
    r = client.post("/upload", data={"albumId": meta["albumId"]}, files=files)
    assert r.status_code == 413


def test_committed_album_refuses(ctx):
    root, client, meta = ctx
    from findme.albums import save_meta

    meta["committed"] = True
    save_meta(root, meta)
    r = client.post(
        "/upload",
        data={"albumId": meta["albumId"]},
        files=[("p0", ("a.jpg", jpeg(), "image/jpeg"))],
    )
    assert r.status_code == 400
