from __future__ import annotations

import json
import re
import time
from pathlib import Path

RING_CAP = 5000
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
    def __init__(self, root: Path, album_id: str, writer_id: str):
        self.path = root / "albums" / album_id / "trace" / f"{writer_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._count = 0

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
        with self.path.open("a") as f:
            f.write(json.dumps(line) + "\n")
        self._count += 1


def writer_for(root: Path, album_id: str | None, writer_id: str) -> TraceWriter | None:
    """TraceWriter for an existing album, else None — avoids creating dirs for bogus ids."""
    if not album_id or not (root / "albums" / album_id / "meta.json").exists():
        return None
    return TraceWriter(root, album_id, writer_id)


def read_merged(root: Path, album_id: str, cursor: int = 0, limit: int = 200) -> tuple[list[dict], int]:
    d = root / "albums" / album_id / "trace"
    events: list[dict] = []
    if d.exists():
        for f in sorted(d.glob("*.jsonl")):
            for line in f.read_text().splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    events.sort(key=lambda e: e.get("ts", 0))
    for i, e in enumerate(events, start=1):
        e["seq"] = i
    page = [e for e in events if e["seq"] > cursor][:limit]
    new_cursor = page[-1]["seq"] if page else cursor
    return page, new_cursor
