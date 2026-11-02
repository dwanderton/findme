from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

DET_SIZE = 640
DET_THRESH = 0.40
NMS_THRESH = 0.40
MIN_QUERY_FACE = 40

DST = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)

DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[3] / "plans" / "reference" / "assets"


def models_dir() -> Path:
    return Path(os.environ.get("FINDME_MODELS_DIR", str(DEFAULT_MODELS_DIR)))


def _nms(dets: np.ndarray, thresh: float) -> list[int]:
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[1:][ovr <= thresh]
    return keep


def _umeyama(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    src_mean, dst_mean = src.mean(0), dst.mean(0)
    src_d, dst_d = src - src_mean, dst - dst_mean
    cov = dst_d.T @ src_d / src.shape[0]
    U, S, Vt = np.linalg.svd(cov)
    d = np.sign(np.linalg.det(U) * np.linalg.det(Vt))
    D = np.diag([1.0, d])
    R = U @ D @ Vt
    var_src = (src_d**2).sum() / src.shape[0]
    scale = (S * np.diag(D)).sum() / var_src
    t = dst_mean - scale * (R @ src_mean)
    return np.concatenate([scale * R, t[:, None]], axis=1)


class Engine:
    def __init__(self, directory: Path | None = None):
        import onnxruntime as ort

        ort.set_default_logger_severity(3)
        d = directory or models_dir()
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        available = ort.get_available_providers()
        wanted = [p for p in providers if p in available]
        self.det = ort.InferenceSession(str(d / "det_10g.onnx"), providers=wanted)
        self.rec = ort.InferenceSession(str(d / "w600k_r50.onnx"), providers=wanted)
        self.det_input = self.det.get_inputs()[0].name
        self.rec_input = self.rec.get_inputs()[0].name
        self.active_provider = self.det.get_providers()[0]

    @property
    def on_gpu(self) -> bool:
        return self.active_provider == "CUDAExecutionProvider"

    def detect(self, rgb: np.ndarray, det_size: int = DET_SIZE) -> list[tuple[np.ndarray, float, np.ndarray]]:
        h0, w0 = rgb.shape[:2]
        scale = min(det_size / w0, det_size / h0)
        nw, nh = int(round(w0 * scale)), int(round(h0 * scale))
        resized = np.asarray(Image.fromarray(rgb).resize((nw, nh), Image.BILINEAR))
        canvas = np.zeros((det_size, det_size, 3), np.uint8)
        canvas[:nh, :nw] = resized
        blob = ((canvas.astype(np.float32) - 127.5) / 128.0).transpose(2, 0, 1)[None]
        outs = self.det.run(None, {self.det_input: blob})
        outs = [o[0] if o.ndim == 3 else o for o in outs]

        all_dets, all_kps = [], []
        for i, stride in enumerate((8, 16, 32)):
            scores = outs[i].ravel()
            bbox_d = outs[i + 3] * stride
            kps_d = outs[i + 6] * stride
            gh, gw = det_size // stride, det_size // stride
            gx, gy = np.meshgrid(np.arange(gw), np.arange(gh))
            centers = np.stack([gx.ravel(), gy.ravel()], -1).astype(np.float32) * stride
            centers = np.repeat(centers, 2, axis=0)
            m = scores >= DET_THRESH
            if not m.any():
                continue
            c, s = centers[m], scores[m]
            b = np.stack(
                [c[:, 0] - bbox_d[m, 0], c[:, 1] - bbox_d[m, 1], c[:, 0] + bbox_d[m, 2], c[:, 1] + bbox_d[m, 3]],
                -1,
            )
            k = kps_d[m].reshape(-1, 5, 2) + c[:, None, :]
            all_dets.append(np.concatenate([b, s[:, None]], -1))
            all_kps.append(k)
        if not all_dets:
            return []
        dets = np.concatenate(all_dets)
        kps = np.concatenate(all_kps)
        keep = _nms(dets, NMS_THRESH)
        return [(dets[i, :4] / scale, float(dets[i, 4]), kps[i] / scale) for i in keep]

    def embed(self, pil_img: Image.Image, kps: np.ndarray) -> np.ndarray:
        M = _umeyama(kps.astype(np.float64), DST.astype(np.float64))
        A, t = M[:, :2], M[:, 2]
        inv = np.linalg.inv(A)
        it = inv @ (np.array([-0.5, -0.5]) - t) + 0.5
        coeffs = (inv[0, 0], inv[0, 1], it[0], inv[1, 0], inv[1, 1], it[1])
        crop = pil_img.transform((112, 112), Image.AFFINE, coeffs, resample=Image.BILINEAR)
        arr = np.asarray(crop, np.float32)
        blob = ((arr - 127.5) / 127.5).transpose(2, 0, 1)[None]
        out = self.rec.run(None, {self.rec_input: blob})[0].ravel().astype(np.float32)
        return out / np.linalg.norm(out)

    def faces_from_bytes(self, data: bytes, retry_large: bool = True):
        pil = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        rgb = np.asarray(pil)
        faces = self.detect(rgb)
        if not faces and retry_large:
            faces = self.detect(rgb, 1280)
        return pil, faces


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine
