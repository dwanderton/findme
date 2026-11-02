import numpy as np
import pytest

from findme.engine import models_dir

MODELS = models_dir()
needs_models = pytest.mark.skipif(
    not (MODELS / "det_10g.onnx").exists(), reason="reference models not staged"
)


@pytest.fixture(scope="module")
def engine():
    from findme.engine import Engine

    return Engine()


@pytest.fixture(scope="module")
def s2a_bytes():
    return (MODELS / "s2_a.jpg").read_bytes()


@needs_models
def test_provider_reported(engine):
    assert engine.active_provider in ("CUDAExecutionProvider", "CPUExecutionProvider")


@needs_models
def test_detects_face_on_s2a(engine, s2a_bytes):
    pil, faces = engine.faces_from_bytes(s2a_bytes)
    assert len(faces) >= 1
    bbox, score, kps = max(faces, key=lambda f: f[0][2] - f[0][0])
    assert bbox[2] - bbox[0] >= 40
    assert score >= 0.4
    assert kps.shape == (5, 2)


@needs_models
def test_embedding_unit_norm(engine, s2a_bytes):
    pil, faces = engine.faces_from_bytes(s2a_bytes)
    _, _, kps = max(faces, key=lambda f: f[0][2] - f[0][0])
    vec = engine.embed(pil, kps)
    assert vec.shape == (512,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-5


@needs_models
def test_no_face_on_flat_image(engine):
    from tests.fixtures import jpeg

    _, faces = engine.faces_from_bytes(jpeg(640, 480))
    assert faces == []
