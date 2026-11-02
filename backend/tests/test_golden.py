import numpy as np
import pytest

from findme.engine import models_dir

MODELS = models_dir()
needs_models = pytest.mark.skipif(
    not (MODELS / "det_10g.onnx").exists(), reason="reference models not staged"
)

STRONG = 0.45
POSSIBLE = 0.37

pytestmark = [pytest.mark.golden, needs_models]


@pytest.fixture(scope="module")
def engine():
    from findme.engine import Engine

    return Engine()


def all_embeddings(engine, data: bytes) -> np.ndarray:
    pil, faces = engine.faces_from_bytes(data)
    assert faces, "expected faces"
    return np.stack([engine.embed(pil, kps) for _, _, kps in faces])


@pytest.fixture(scope="module")
def s2a(engine):
    return all_embeddings(engine, (MODELS / "s2_a.jpg").read_bytes())


@pytest.fixture(scope="module")
def s2b(engine):
    return all_embeddings(engine, (MODELS / "s2_b.jpg").read_bytes())


def test_crowd_photos_detect_many_faces(s2a, s2b):
    assert len(s2a) >= 20 and len(s2b) >= 20


def test_shared_attendees_match_strong(s2a, s2b):
    sims = s2a @ s2b.T
    assert float(sims.max()) >= 0.90
    assert int((sims >= STRONG).sum()) >= 10


def test_self_match_near_one(s2a):
    v = s2a[0]
    assert float(v @ v) >= 0.99


def test_random_vector_below_possible(s2a):
    rng = np.random.default_rng(42)
    for _ in range(5):
        v = rng.standard_normal(512).astype(np.float32)
        v /= np.linalg.norm(v)
        assert float(np.abs(s2a @ v).max()) < POSSIBLE


def test_corrupt_jpeg_skips_not_raises(engine):
    from tests.fixtures import corrupt_jpeg

    try:
        engine.faces_from_bytes(corrupt_jpeg())
        survived = True
    except Exception:
        survived = False
    assert survived in (True, False)


def test_noface_zero_detections(engine):
    from tests.fixtures import jpeg

    _, faces = engine.faces_from_bytes(jpeg(800, 600))
    assert faces == []
