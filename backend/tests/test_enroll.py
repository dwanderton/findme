import numpy as np
import pytest
from fastapi.testclient import TestClient

import findme.routes.enroll as enroll_route
from findme.app.factory import create_app
from findme.engine import models_dir
from findme.faces import load_refs
from tests.fixtures import jpeg

MODELS = models_dir()
needs_models = pytest.mark.skipif(
    not (MODELS / "det_10g.onnx").exists(), reason="reference models not staged"
)


class FakeEngine:
    def faces_from_bytes(self, data, retry_large=True):
        if data[:1] == b"\xff" and len(data) > 1000:
            return "pil", [(np.array([10.0, 10.0, 110.0, 120.0]), 0.92, np.zeros((5, 2)))]
        return "pil", []

    def embed(self, pil, kps):
        v = np.ones(512, np.float32)
        return v / np.linalg.norm(v)


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(enroll_route, "get_engine", lambda: FakeEngine())
    app = create_app(tmp_path)
    return tmp_path, TestClient(app, raise_server_exceptions=False)


def selfie(n=1):
    return [(f"s{i}", (f"s{i}.jpg", jpeg(400, 300), "image/jpeg")) for i in range(n)]


def test_single_selfie_enrolls(ctx):
    root, client = ctx
    r = client.post("/enroll", files=selfie(1))
    assert r.status_code == 200
    body = r.json()
    assert load_refs(root, body["userId"]).shape == (1, 512)
    assert body["faces"][0]["facePx"] == 100


def test_five_selfies_ok_sixth_rejected_via_patch(ctx):
    root, client = ctx
    r = client.post("/enroll", files=selfie(5))
    assert r.status_code == 200
    uid = r.json()["userId"]
    r2 = client.patch("/enroll", data={"userId": uid}, files=selfie(1))
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "TOO_MANY_SELFIES"
    assert load_refs(root, uid).shape == (5, 512)


def test_patch_appends(ctx):
    root, client = ctx
    uid = client.post("/enroll", files=selfie(2)).json()["userId"]
    r = client.patch("/enroll", data={"userId": uid}, files=selfie(2))
    assert r.status_code == 200
    assert load_refs(root, uid).shape == (4, 512)
    assert r.json()["faces"][0]["selfie"] == 2


def test_no_face_names_selfie(ctx):
    _, client = ctx
    files = selfie(1) + [("s9", ("tiny.jpg", jpeg(8, 8), "image/jpeg"))]
    r = client.post("/enroll", files=files)
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "NO_FACE_IN_SELFIE" and err["selfie"] == 1


@needs_models
def test_real_engine_end_to_end(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app)
    data = (MODELS / "s2_a.jpg").read_bytes()
    r = client.post("/enroll", files=[("s0", ("me.jpg", data, "image/jpeg"))])
    assert r.status_code == 200
    body = r.json()
    assert body["faces"][0]["facePx"] >= 40
    assert load_refs(tmp_path, body["userId"]).shape == (1, 512)
