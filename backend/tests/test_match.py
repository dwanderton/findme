import numpy as np

from findme.match import GATE_PX, POSSIBLE, STRONG, band_for, search


def unit(v):
    v = np.asarray(v, np.float32)
    return v / np.linalg.norm(v)


def person_basis(seed: int, n: int = 3):
    rng = np.random.default_rng(seed)
    base = unit(rng.standard_normal(512))
    out = []
    for _ in range(n):
        tilt = unit(rng.standard_normal(512))
        out.append(unit(0.92 * base + 0.39 * tilt))
    return base, out


def test_band_boundaries_exact():
    assert band_for(STRONG) == "strong"
    assert band_for(STRONG - 1e-9) == "possible"
    assert band_for(POSSIBLE) == "possible"
    assert band_for(POSSIBLE - 1e-9) is None


def test_simple_match_and_rank():
    me, views = person_basis(1)
    other, _ = person_basis(2)
    emb = np.stack([views[0], views[1], other])
    face_px = np.array([100, 100, 100])
    img_idx = np.array([0, 1, 2])
    matches, refs = search(emb, face_px, img_idx, me[None])
    photos = [m.photo for m in matches]
    assert 0 in photos and 1 in photos and 2 not in photos
    assert matches[0].score >= matches[-1].score


def test_gate_px_excludes_small_faces():
    me, views = person_basis(3)
    emb = np.stack([views[0]])
    matches, _ = search(emb, np.array([GATE_PX - 1]), np.array([0]), me[None])
    assert matches == []


def test_max_over_refs_ignites_profile():
    rng = np.random.default_rng(7)
    frontal = unit(rng.standard_normal(512))
    profile = unit(rng.standard_normal(512))
    index_face = unit(0.9 * profile + 0.44 * unit(rng.standard_normal(512)))
    assert float(index_face @ frontal) < 0.52
    assert float(index_face @ profile) >= 0.52
    emb = index_face[None]
    px, idx = np.array([100]), np.array([0])
    only_frontal, _ = search(emb, px, idx, frontal[None])
    both, _ = search(emb, px, idx, np.stack([frontal, profile]))
    assert [m.photo for m in both] == [0]
    assert only_frontal == [] or only_frontal[0].score < both[0].score


def test_bootstrap_promotes_same_person():
    me, views = person_basis(11, n=6)
    hard = unit(0.80 * me + 0.60 * unit(np.random.default_rng(99).standard_normal(512)))
    emb = np.stack(views[:4] + [hard])
    face_px = np.array([100, 100, 100, 100, 100])
    img_idx = np.arange(5)
    selfie = views[5]
    solo = float(hard @ selfie)
    matches, refs_used = search(emb, face_px, img_idx, selfie[None])
    assert refs_used > 1
    scored = {m.photo: m.score for m in matches}
    if 4 in scored:
        assert scored[4] >= solo - 0.05


def test_per_photo_max_over_faces():
    me, views = person_basis(21)
    other, _ = person_basis(22)
    emb = np.stack([views[0], other])
    face_px = np.array([100, 100])
    img_idx = np.array([0, 0])
    matches, _ = search(emb, face_px, img_idx, me[None])
    assert len(matches) == 1
    assert matches[0].face_row == 0


def test_empty_inputs():
    assert search(np.zeros((0, 512), np.float32), np.array([]), np.array([]), np.zeros((1, 512)))[0] == []
