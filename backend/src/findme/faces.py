from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np

from findme.errors import ApiError
from findme.validate import MAX_SELFIES


def faces_path(root: Path, user_id: str) -> Path:
    return root / "faces" / f"{user_id}.npy"


def save_refs(root: Path, user_id: str | None, vecs: np.ndarray) -> str:
    user_id = user_id or str(uuid.uuid4())
    p = faces_path(root, user_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp.npy")
    np.save(tmp, vecs.astype(np.float32))
    tmp.replace(p)
    return user_id


def load_refs(root: Path, user_id: str) -> np.ndarray:
    p = faces_path(root, user_id)
    if not p.exists():
        raise ApiError("UNKNOWN_USER", "User not found.")
    return np.load(p)


def append_refs(root: Path, user_id: str, vecs: np.ndarray) -> np.ndarray:
    existing = load_refs(root, user_id)
    combined = np.vstack([existing, vecs.astype(np.float32)])
    if combined.shape[0] > MAX_SELFIES:
        raise ApiError("TOO_MANY_SELFIES", f"Reference set caps at {MAX_SELFIES} selfies.")
    save_refs(root, user_id, combined)
    return combined
