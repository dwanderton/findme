from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CONFIRM_SIM = 0.52
CONFIRM_PX = 64
MAX_REFS = 10
GATE_PX = 56
STRONG = 0.45
POSSIBLE = 0.37


@dataclass
class PhotoMatch:
    photo: int
    score: float
    band: str
    face_row: int


def band_for(score: float) -> str | None:
    if score >= STRONG:
        return "strong"
    if score >= POSSIBLE:
        return "possible"
    return None


def search(
    emb: np.ndarray,
    face_px: np.ndarray,
    img_idx: np.ndarray,
    refs: np.ndarray,
) -> tuple[list[PhotoMatch], int]:
    if emb.size == 0 or refs.size == 0:
        return [], refs.shape[0] if refs.ndim == 2 else 0
    refs = np.atleast_2d(refs).astype(np.float32)

    pass1 = (emb @ refs.T).max(axis=1)

    conf = np.where((face_px >= CONFIRM_PX) & (pass1 >= CONFIRM_SIM))[0]
    conf = conf[np.argsort(-pass1[conf])][:MAX_REFS]
    Q = np.vstack([refs, emb[conf]]) if conf.size else refs

    S = emb @ Q.T
    if Q.shape[0] >= 3:
        score = np.sort(S, axis=1)[:, -3:].mean(axis=1)
    else:
        score = S.max(axis=1)

    gate = face_px >= GATE_PX
    best: dict[int, tuple[float, int]] = {}
    for i in np.where(gate & (score >= POSSIBLE))[0]:
        p = int(img_idx[i])
        if p not in best or score[i] > best[p][0]:
            best[p] = (float(score[i]), int(i))

    ranked = sorted(best.items(), key=lambda kv: -kv[1][0])
    return [
        PhotoMatch(photo=p, score=round(sc, 4), band=band_for(sc), face_row=i)
        for p, (sc, i) in ranked
    ], int(Q.shape[0])
