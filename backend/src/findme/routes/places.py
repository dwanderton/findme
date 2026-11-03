from __future__ import annotations

import httpx
from fastapi import APIRouter, Query

from findme.places import autocomplete

router = APIRouter()


@router.get("/places/autocomplete")
async def places_autocomplete(
    q: str = Query(min_length=3, max_length=120), session: str = Query(min_length=8)
):
    async with httpx.AsyncClient() as client:
        return await autocomplete(client, q, session)
