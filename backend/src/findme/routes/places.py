from __future__ import annotations

import httpx
from fastapi import APIRouter, Query, Request

from findme.places import autocomplete
from findme.trace import writer_for

router = APIRouter()


@router.get("/places/autocomplete")
async def places_autocomplete(
    request: Request,
    q: str = Query(min_length=3, max_length=120),
    session: str = Query(min_length=8),
    albumId: str | None = Query(default=None),
):
    trace = writer_for(request.app.state.root, albumId, "places")
    rid = request.headers.get("x-request-id", "")
    async with httpx.AsyncClient() as client:
        return await autocomplete(client, q, session, trace=trace, request_id=rid)
