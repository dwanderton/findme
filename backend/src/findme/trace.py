from __future__ import annotations

import json
import re
import time
from pathlib import Path

RING_CAP = 5000
FILE_CAP_BYTES = 2_000_000  # short-lived writers (one per request) can't rely on RING_CAP
REDACT = re.compile(r"(key|token|secret|authorization|signature)", re.I)


def _redact(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if REDACT.search(str(k)):
            continue
        if isinstance(v, str) and ("http" in v and ("key=" in v or "token=" in v)):
            continue
        if isinstance(v, (bytes, bytearray)):
            continue
        out[k] = v
    return out


class TraceWriter:
    def __init__(self, root: Path, album_id: str | None, writer_id: str):
        # album_id=None targets the global scope: requests that belong to no album
        # (warmup pings, autocomplete before an album exists) still get traced.
        base = root / "albums" / album_id / "trace" if album_id else root / "trace"
        self.path = base / f"{writer_id}.jsonl"
        self._count = 0
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size > FILE_CAP_BYTES:
                self._count = RING_CAP
        except OSError:
            self._count = RING_CAP

    def emit(self, src: str, event: str, level: str = "info", request_id: str = "", **data) -> None:
        if self._count >= RING_CAP:
            return
        line = {
            "ts": time.time(),
            "src": src,
            "level": level,
            "requestId": request_id,
            "event": event,
            "data": _redact(data),
        }
        # Tracing must never take a pipeline down: an album deleted mid-job makes
        # this path vanish, which is a dropped line, not a crash.
        try:
            with self.path.open("a") as f:
                f.write(json.dumps(line) + "\n")
        except OSError:
            return
        self._count += 1


def writer_for(root: Path, album_id: str | None, writer_id: str) -> TraceWriter | None:
    """TraceWriter for an existing album, else None — avoids creating dirs for bogus ids."""
    if not album_id or not (root / "albums" / album_id / "meta.json").exists():
        return None
    return TraceWriter(root, album_id, writer_id)


def global_writer(root: Path, writer_id: str) -> TraceWriter:
    return TraceWriter(root, None, writer_id)


def _read_dir(d: Path, events: list[dict]) -> None:
    if not d.exists():
        return
    for f in sorted(d.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue


def read_merged(root: Path, album_id: str, cursor: int = 0, limit: int = 200) -> tuple[list[dict], int]:
    events: list[dict] = []
    _read_dir(root / "albums" / album_id / "trace", events)
    _read_dir(root / "trace", events)
    events.sort(key=lambda e: e.get("ts", 0))
    for i, e in enumerate(events, start=1):
        e["seq"] = i
    page = [e for e in events if e["seq"] > cursor][:limit]
    new_cursor = page[-1]["seq"] if page else cursor
    return page, new_cursor
