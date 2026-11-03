from __future__ import annotations

import asyncio
import random
import time
from urllib.parse import urlparse

import httpx

TIMEOUT_S = 3.0
RETRIES = 2
BACKOFFS_S = (0.25, 1.0)
CIRCUIT_OPEN_S = 60.0
RETRY_AFTER_CAP_S = 3.0


class Circuit:
    def __init__(self, name: str):
        self.name = name
        self.open_until = 0.0

    @property
    def state(self) -> str:
        return "open" if time.monotonic() < self.open_until else "closed"

    def trip(self) -> None:
        self.open_until = time.monotonic() + CIRCUIT_OPEN_S


class UpstreamDown(Exception):
    pass


def emit_external(trace, event: str, level: str = "info", request_id: str = "", **data) -> None:
    """Best-effort external-call trace; trace is a TraceWriter or None."""
    if trace is None:
        return
    try:
        trace.emit("external", event, level=level, request_id=request_id, **data)
    except OSError:
        pass


async def get_json(
    client: httpx.AsyncClient,
    circuit: Circuit,
    url: str,
    params: dict,
    sleep=asyncio.sleep,
    trace=None,
    request_id: str = "",
) -> dict:
    host = urlparse(url).netloc
    if circuit.state == "open":
        emit_external(trace, circuit.name, level="warn", request_id=request_id, host=host, skipped="circuit-open")
        raise UpstreamDown(f"{circuit.name} circuit open")
    last: Exception | None = None
    for attempt in range(RETRIES + 1):
        started = time.monotonic()
        try:
            resp = await client.get(url, params=params, timeout=TIMEOUT_S)
            ms = round((time.monotonic() - started) * 1000)
            if resp.status_code == 429:
                emit_external(trace, circuit.name, level="warn", request_id=request_id, host=host, status=429, ms=ms, attempt=attempt)
                if attempt >= RETRIES:
                    break
                ra = resp.headers.get("Retry-After")
                delay = BACKOFFS_S[attempt] * (1 + random.random() * 0.25)
                if ra:
                    try:
                        ra_s = float(ra)
                        if ra_s <= RETRY_AFTER_CAP_S:
                            delay = ra_s
                        else:
                            break
                    except ValueError:
                        pass
                await sleep(delay)
                continue
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError("server error", request=resp.request, response=resp)
            resp.raise_for_status()
            emit_external(trace, circuit.name, request_id=request_id, host=host, status=resp.status_code, ms=ms, attempt=attempt)
            return resp.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as e:
            last = e
            ms = round((time.monotonic() - started) * 1000)
            status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
            emit_external(trace, circuit.name, level="warn", request_id=request_id, host=host, status=status, ms=ms, attempt=attempt, error=type(e).__name__)
            if attempt >= RETRIES:
                break
            await sleep(BACKOFFS_S[attempt] * (1 + random.random() * 0.25))
    circuit.trip()
    emit_external(trace, "circuit.open", level="error", request_id=request_id, api=circuit.name, host=host)
    raise UpstreamDown(f"{circuit.name} failed: {last}")
