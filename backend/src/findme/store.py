from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA = pa.schema(
    [
        ("photo_id", pa.string()),
        ("face_i", pa.int32()),
        ("bbox", pa.list_(pa.int32(), 4)),
        ("vec", pa.list_(pa.float32(), 512)),
        ("face_px", pa.int32()),
    ]
)


def album_dir(root: Path, album_id: str) -> Path:
    return root / "albums" / album_id


def shard_path(root: Path, album_id: str, batch_id: str) -> Path:
    return album_dir(root, album_id) / f"index-{batch_id}.parquet"


def write_shard(root: Path, album_id: str, batch_id: str, rows: list[dict]) -> Path:
    path = shard_path(root, album_id, batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {
        "photo_id": [r["photo_id"] for r in rows],
        "face_i": [r["face_i"] for r in rows],
        "bbox": [list(map(int, r["bbox"])) for r in rows],
        "vec": [np.asarray(r["vec"], np.float32).tolist() for r in rows],
        "face_px": [int(r["face_px"]) for r in rows],
    }
    table = pa.table(arrays, schema=SCHEMA)
    tmp = path.with_suffix(".tmp")
    pq.write_table(table, tmp)
    tmp.replace(path)
    return path


def load_index(root: Path, album_id: str):
    d = album_dir(root, album_id)
    shards = sorted(d.glob("index-*.parquet"))
    if not shards:
        return np.zeros((0, 512), np.float32), np.array([], np.int32), [], []
    tables = [pq.read_table(s) for s in shards]
    table = pa.concat_tables(tables)
    emb = np.stack([np.asarray(v, np.float32) for v in table["vec"].to_pylist()]) if table.num_rows else np.zeros((0, 512), np.float32)
    face_px = np.asarray(table["face_px"].to_pylist(), np.int32)
    photo_ids = table["photo_id"].to_pylist()
    bboxes = table["bbox"].to_pylist()
    return emb, face_px, photo_ids, bboxes


def index_mtime(root: Path, album_id: str) -> float:
    shards = list(album_dir(root, album_id).glob("index-*.parquet"))
    return max((s.stat().st_mtime for s in shards), default=0.0)


def write_counter(root: Path, album_id: str, stage: str, key: str, data: dict) -> None:
    d = album_dir(root, album_id) / "status"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{stage}-{key}.tmp"
    tmp.write_text(json.dumps(data))
    tmp.replace(d / f"{stage}-{key}.json")


def aggregate_counters(root: Path, album_id: str) -> dict:
    d = album_dir(root, album_id) / "status"
    out: dict[str, dict] = {}
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        stage = f.name.split("-", 1)[0]
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        agg = out.setdefault(stage, {})
        for k, v in data.items():
            if isinstance(v, (int, float)):
                agg[k] = agg.get(k, 0) + v
            else:
                agg[k] = v
    return out
