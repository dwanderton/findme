import numpy as np
import pytest
from fastapi.testclient import TestClient

from findme.app.factory import create_app
from findme.faces import save_refs
from tests.fixtures import jpeg

VENUE = {"label": "Shoreline Amphitheatre", "lat": 37.4267, "lon": -122.0806}


@pytest.fixture
def ctx(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app, raise_server_exceptions=False)
    body = client.post("/albums", json={"photoCount": 2}).json()
    client.post(
        "/upload",
        data={"albumId": body["albumId"]},
        files=[("p0", ("a.jpg", jpeg(), "image/jpeg"))],
    )
    return tmp_path, client, body["albumId"], body["ownerToken"]


def test_venue_link_unlink_owner_gated(ctx):
    _, client, album_id, token = ctx
    r = client.patch(f"/albums/{album_id}/venue", json={"venue": VENUE})
    assert r.status_code == 403
    r = client.patch(f"/albums/{album_id}/venue", json={"venue": VENUE}, headers={"X-Owner-Token": token})
    assert r.status_code == 200
    assert r.json()["venue"]["source"] == "user"
    r = client.delete(f"/albums/{album_id}/venue", headers={"X-Owner-Token": token})
    assert r.status_code == 204


def test_album_delete_erases(ctx):
    root, client, album_id, token = ctx
    r = client.delete(f"/albums/{album_id}", headers={"X-Owner-Token": "wrong"})
    assert r.status_code == 403
    r = client.delete(f"/albums/{album_id}", headers={"X-Owner-Token": token})
    assert r.status_code == 204
    assert client.get(f"/albums/{album_id}/status").status_code == 404
    assert not (root / "albums" / album_id).exists()


def test_user_delete(ctx):
    root, client, *_ = ctx
    uid = save_refs(root, None, np.ones((1, 512), np.float32))
    assert (root / "faces" / f"{uid}.npy").exists()
    r = client.delete(f"/users/{uid}")
    assert r.status_code == 204
    assert not (root / "faces" / f"{uid}.npy").exists()
