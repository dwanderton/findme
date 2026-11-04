from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Request

from findme.engine import MIN_QUERY_FACE, get_engine
from findme.errors import ApiError
from findme.faces import append_refs, load_refs, save_refs
from findme.validate import MAX_SELFIE_BYTES, check_image, check_selfie_count

router = APIRouter()


async def _embed_selfies(request: Request, existing: int) -> tuple[list[np.ndarray], list[dict]]:
    form = await request.form()
    files = [(k, v) for k, v in form.multi_items() if hasattr(v, "read")]
    check_selfie_count(existing, len(files))
    engine = get_engine()
    vecs, faces = [], []
    for i, (key, f) in enumerate(files):
        data = await f.read()
        check_image(data, max_bytes=MAX_SELFIE_BYTES, name=f.filename or key)
        pil, detections = engine.faces_from_bytes(data)
        if not detections:
            raise ApiError("NO_FACE_IN_SELFIE", "No face found. Try a clearer, frontal shot.", selfie=i)
        bbox, _, kps = max(detections, key=lambda d: d[0][2] - d[0][0])
        face_px = int(bbox[2] - bbox[0])
        if face_px < MIN_QUERY_FACE:
            raise ApiError("NO_FACE_IN_SELFIE", "The largest face is too small. Try a closer photo.", selfie=i)
        vecs.append(engine.embed(pil, kps))
        faces.append(
            {
                "selfie": existing + i,
                "facePx": face_px,
                "quality": round(float(max(d[1] for d in detections)), 2),
                "multipleFaces": len(detections) > 1,
            }
        )
    return vecs, faces


@router.post("/enroll")
async def enroll(request: Request):
    root = request.app.state.root
    vecs, faces = await _embed_selfies(request, existing=0)
    user_id = save_refs(root, None, np.stack(vecs))
    return {"userId": user_id, "faces": faces}


# PUT alongside PATCH: some Runpod LB gateways drop PATCH before it reaches the worker.
@router.api_route("/enroll", methods=["PATCH", "PUT"])
async def enroll_append(request: Request):
    root = request.app.state.root
    form = await request.form()
    user_id = form.get("userId")
    if not user_id:
        raise ApiError("UNKNOWN_USER", "userId is required.")
    existing = load_refs(root, str(user_id)).shape[0]
    vecs, faces = await _embed_selfies(request, existing=existing)
    append_refs(root, str(user_id), np.stack(vecs))
    return {"userId": user_id, "faces": faces}
