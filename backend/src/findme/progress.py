from __future__ import annotations

from dataclasses import dataclass

EWMA_WINDOW_S = 30.0
MIN_PCT = 10.0
MIN_SAMPLE_S = 10.0


@dataclass
class EtaResult:
    rate: float
    eta_sec: int | None
    confident: bool


class EtaCalculator:
    def __init__(self):
        self.samples: list[tuple[float, int]] = []

    def observe(self, ts: float, done: int) -> None:
        self.samples.append((ts, done))
        cutoff = ts - EWMA_WINDOW_S * 2
        self.samples = [s for s in self.samples if s[0] >= cutoff]

    def compute(self, now: float, done: int, total: int, workers_initializing: int = 0) -> EtaResult:
        window = [s for s in self.samples if s[0] >= now - EWMA_WINDOW_S]
        rate = 0.0
        if len(window) >= 2:
            dt = window[-1][0] - window[0][0]
            dd = window[-1][1] - window[0][1]
            if dt > 0:
                rate = dd / dt
        span = (self.samples[-1][0] - self.samples[0][0]) if len(self.samples) >= 2 else 0.0
        pct = (done / total * 100) if total else 0.0
        confident = (
            rate > 0
            and pct >= MIN_PCT
            and span >= MIN_SAMPLE_S
            and workers_initializing == 0
        )
        eta = None
        if confident:
            remaining = max(total - done, 0)
            eta = int(round(remaining / rate / 5.0) * 5)
        return EtaResult(rate=round(rate, 2), eta_sec=eta, confident=confident)


def progress_event(seq: int, stage: str, done: int, total: int, faces: int, eta: EtaResult, workers: dict) -> dict:
    return {
        "seq": seq,
        "stage": stage,
        "photosDone": done,
        "photosTotal": total,
        "facesFound": faces,
        "pct": round(done / total * 100, 1) if total else 0.0,
        "rate": {"photosPerSec": eta.rate, "windowSec": int(EWMA_WINDOW_S)},
        "etaSec": eta.eta_sec,
        "etaConfident": eta.confident,
        "workers": workers,
    }
