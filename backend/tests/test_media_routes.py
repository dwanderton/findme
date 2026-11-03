import io
import zipfile

import numpy as np
import piexif
import pytest
from fastapi.testclient import TestClient

from findme.albums import load_meta, save_meta
from findme.app.factory import create_app
from findme.faces import save_refs
from findme.jobs.index_gpu import run_all_batches
from tests.test_index_gpu import FakeEngine
from tests.test_media import noise_jpeg


@pytest.fixture
def ctx(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    album_id = client.post("/albums", json={"photoCount": 3}).json()["albumId"]
    files = [(f"p{i}", (f"{i}.jpg", noise_jpeg(i), "image/jpeg")) for i in range(3)]
    client.post("/upload", data={"albumId": album_id}, files=files)
    client.post(f"/albums/{album_id}/commit", json={"uploaded": 3})
    run_all_batches(tmp_path, album_id, engine=FakeEngine())
    user_id = save_refs(tmp_path, None, np.ones((1, 512), np.float32) / np.sqrt(512))
    meta = load_meta(tmp_path, album_id)
    photo_ids = sorted(meta["photos"])
    app.state.find_grants = {user_id: set(photo_ids[:2])}
    return tmp_path, client, album_id, user_id, photo_ids


def test_photo_and_thumb_serving(ctx):
    _, client, album_id, user_id, photo_ids = ctx
    r = client.get(f"/photos/{photo_ids[0]}", params={"userId": user_id, "albumId": album_id})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    r = client.get(f"/photos/{photo_ids[0]}", params={"userId": user_id, "albumId": album_id, "thumb": True})
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"


def test_ungranted_photo_404(ctx):
    _, client, album_id, user_id, photo_ids = ctx
    r = client.get(f"/photos/{photo_ids[2]}", params={"userId": user_id, "albumId": album_id})
    assert r.status_code == 404


def test_download_zip_with_sidecar_and_venue_exif(ctx):
    root, client, album_id, user_id, photo_ids = ctx
    meta = load_meta(root, album_id)
    meta["venue"] = {"label": "Shoreline Amphitheatre", "lat": 37.4267, "lon": -122.0806, "source": "user"}
    first = sorted(meta["photos"])[0]
    meta["photos"][first].setdefault("exif", {}).update({"taken_at": "2026-06-01T15:30", "taken_at_source": "user"})
    save_meta(root, meta)
    r = client.get(f"/albums/{album_id}/download", params={"userId": user_id})
    assert r.status_code == 200
    assert r.headers["x-parts"] == "1"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert "findme.json" in names
    photo_names = [n for n in names if n.startswith("photos/")]
    assert len(photo_names) == 2
    exif = piexif.load(z.read(photo_names[0]))
    assert exif["GPS"], "venue GPS written into zip copy"
    assert b"Shoreline Amphitheatre" in exif["0th"][piexif.ImageIFD.ImageDescription]
    assert exif["Exif"][piexif.ExifIFD.DateTimeOriginal] == b"2026:06:01 15:30"
    original = (root / "albums" / album_id / "photos" / f"{first}.jpg").read_bytes()
    assert not piexif.load(original)["GPS"], "volume original untouched"


def test_download_without_find_grant_404(ctx):
    _, client, album_id, _, _ = ctx
    user2 = save_refs(client.app.state.root, None, np.ones((1, 512), np.float32))
    r = client.get(f"/albums/{album_id}/download", params={"userId": user2})
    assert r.status_code == 404


def test_part_splitting(ctx, monkeypatch):
    import findme.settings as settings

    root, client, album_id, user_id, _ = ctx
    monkeypatch.setattr(settings, "ZIP_PART_LIMIT", 2000)
    r1 = client.get(f"/albums/{album_id}/download", params={"userId": user_id})
    assert int(r1.headers["x-parts"]) >= 2
    r2 = client.get(f"/albums/{album_id}/download", params={"userId": user_id, "part": int(r1.headers["x-parts"])})
    assert r2.status_code == 200
    r3 = client.get(f"/albums/{album_id}/download", params={"userId": user_id, "part": 99})
    assert r3.status_code == 404
