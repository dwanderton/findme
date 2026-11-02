from __future__ import annotations

import asyncio
import random
import time

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


async def get_json(
    client: httpx.AsyncClient,
    circuit: Circuit,
    url: str,
    params: dict,
    sleep=asyncio.sleep,
) -> dict:
    if circuit.state == "open":
        raise UpstreamDown(f"{circuit.name} circuit open")
    last: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            resp = await client.get(url, params=params, timeout=TIMEOUT_S)
            if resp.status_code == 429:
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
            return resp.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as e:
            last = e
            if attempt >= RETRIES:
                break
            await sleep(BACKOFFS_S[attempt] * (1 + random.random() * 0.25))
    circuit.trip()
    raise UpstreamDown(f"{circuit.name} failed: {last}")
