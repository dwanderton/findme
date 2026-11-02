import numpy as np
import pytest
from fastapi.testclient import TestClient

from findme.albums import load_meta
from findme.app.factory import create_app
from findme.jobs.index_gpu import run_all_batches, run_gpu_batch
from findme.store import load_index
from tests.fixtures import jpeg


class FakeEngine:
    active_provider = "CPUExecutionProvider"

    def __init__(self):
        self.rng = np.random.default_rng(0)

    def faces_from_bytes(self, data, retry_large=False):
        return "pil", [
            (np.array([0.0, 0.0, 80.0, 90.0]), 0.9, np.zeros((5, 2))),
            (np.array([0.0, 0.0, 40.0, 50.0]), 0.8, np.zeros((5, 2))),
        ]

    def embed(self, pil, kps):
        v = self.rng.standard_normal(512).astype(np.float32)
        return v / np.linalg.norm(v)


@pytest.fixture
def ctx(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app)
    album_id = client.post("/albums", json={"photoCount": 4}).json()["albumId"]
    files = [(f"p{i}", (f"{i}.jpg", jpeg(200 + i, 150), "image/jpeg")) for i in range(4)]
    client.post("/upload", data={"albumId": album_id}, files=files)
    client.post(f"/albums/{album_id}/commit", json={"uploaded": 4})
    return tmp_path, album_id


def test_batch_embeds_gated_faces(ctx):
    root, album_id = ctx
    r = run_gpu_batch(root, album_id, "0", engine=FakeEngine())
    assert r["faces"] == 4
    emb, face_px, photo_ids, _ = load_index(root, album_id)
    assert emb.shape == (4, 512)
    assert all(px >= 56 for px in face_px)


def test_rerun_idempotent_and_ready(ctx):
    root, album_id = ctx
    run_all_batches(root, album_id, engine=FakeEngine())
    run_gpu_batch(root, album_id, "0", engine=FakeEngine())
    emb, *_ = load_index(root, album_id)
    assert emb.shape == (4, 512)
    assert load_meta(root, album_id)["stage"] == "ready"


def test_missing_photo_recorded_batch_survives(ctx):
    root, album_id = ctx
    meta = load_meta(root, album_id)
    victim = meta["batches"]["0"]["photos"][0]
    (root / "albums" / album_id / "photos" / f"{victim}.jpg").unlink()
    r = run_gpu_batch(root, album_id, "0", engine=FakeEngine())
    assert victim in r["failures"]
    assert r["faces"] == 3
