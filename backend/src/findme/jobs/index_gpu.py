from __future__ import annotations

from pathlib import Path

from findme.albums import load_meta, save_meta
from findme.engine import get_engine
from findme.match import GATE_PX
from findme.store import album_dir, write_counter, write_shard
from findme.trace import TraceWriter


def run_gpu_batch(root: Path, album_id: str, batch_id: str, engine=None) -> dict:
    engine = engine or get_engine()
    trace = TraceWriter(root, album_id, f"gpu-{batch_id}")
    trace.emit("gpu-qb", "batch.start", batch=batch_id, provider=getattr(engine, "active_provider", "unknown"))

    meta = load_meta(root, album_id)
    batch = meta["batches"][batch_id]
    photos_dir = album_dir(root, album_id) / "photos"

    rows, failures, done = [], [], 0
    for photo_id in batch["photos"]:
        p = photos_dir / f"{photo_id}.jpg"
        if not p.exists():
            failures.append(photo_id)
            continue
        try:
            pil, faces = engine.faces_from_bytes(p.read_bytes(), retry_large=False)
        except Exception:
            failures.append(photo_id)
            trace.emit("gpu-qb", "photo.failed", level="warn", photoId=photo_id)
            continue
        for i, (bbox, _score, kps) in enumerate(faces):
            face_px = int(bbox[2] - bbox[0])
            if face_px < GATE_PX:
                continue
            rows.append(
                {
                    "photo_id": photo_id,
                    "face_i": i,
                    "bbox": [int(v) for v in bbox],
                    "vec": engine.embed(pil, kps),
                    "face_px": face_px,
                }
            )
        done += 1

    if rows:
        write_shard(root, album_id, batch_id, rows)
    write_counter(root, album_id, "embedding", batch_id, {"photosDone": done, "facesFound": len(rows)})
    trace.emit("gpu-qb", "batch.done", batch=batch_id, faces=len(rows), failed=len(failures))

    meta = load_meta(root, album_id)
    meta["batches"][batch_id]["done"] = True
    if all(b["done"] for b in meta["batches"].values()):
        meta["stage"] = "ready"
    save_meta(root, meta)
    return {"batch": batch_id, "faces": len(rows), "failures": failures}


def run_all_batches(root: Path, album_id: str, engine=None) -> dict:
    meta = load_meta(root, album_id)
    results = [run_gpu_batch(root, album_id, bid, engine=engine) for bid in meta["batches"]]
    return {"batches": len(results), "faces": sum(r["faces"] for r in results)}
