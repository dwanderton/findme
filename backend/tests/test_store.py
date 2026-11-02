import numpy as np

from findme.store import aggregate_counters, index_mtime, load_index, write_counter, write_shard


def rows(n, start=0):
    rng = np.random.default_rng(start)
    return [
        {
            "photo_id": f"photo-{start + i}",
            "face_i": 0,
            "bbox": [1, 2, 3, 4],
            "vec": rng.standard_normal(512).astype(np.float32),
            "face_px": 80,
        }
        for i in range(n)
    ]


def test_write_and_load_roundtrip(tmp_path):
    write_shard(tmp_path, "a1", "b0", rows(3))
    write_shard(tmp_path, "a1", "b1", rows(2, start=3))
    emb, face_px, photo_ids, bboxes = load_index(tmp_path, "a1")
    assert emb.shape == (5, 512)
    assert emb.dtype == np.float32
    assert len(photo_ids) == 5 and photo_ids[0] == "photo-0"
    assert list(face_px) == [80] * 5
    assert bboxes[0] == [1, 2, 3, 4]


def test_rewrite_same_batch_idempotent(tmp_path):
    write_shard(tmp_path, "a1", "b0", rows(3))
    write_shard(tmp_path, "a1", "b0", rows(3))
    emb, *_ = load_index(tmp_path, "a1")
    assert emb.shape == (3, 512)


def test_empty_album(tmp_path):
    emb, face_px, photo_ids, bboxes = load_index(tmp_path, "missing")
    assert emb.shape == (0, 512) and photo_ids == []


def test_mtime_moves_on_write(tmp_path):
    assert index_mtime(tmp_path, "a1") == 0.0
    write_shard(tmp_path, "a1", "b0", rows(1))
    assert index_mtime(tmp_path, "a1") > 0.0


def test_counters_aggregate_across_writers(tmp_path):
    write_counter(tmp_path, "a1", "embedding", "b0", {"photosDone": 50, "facesFound": 120})
    write_counter(tmp_path, "a1", "embedding", "b1", {"photosDone": 43, "facesFound": 97})
    write_counter(tmp_path, "a1", "extracting", "cpu", {"photosDone": 93, "photosTotal": 93})
    agg = aggregate_counters(tmp_path, "a1")
    assert agg["embedding"] == {"photosDone": 93, "facesFound": 217}
    assert agg["extracting"]["photosTotal"] == 93
