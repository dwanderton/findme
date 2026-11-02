from __future__ import annotations

from fastapi import APIRouter, Header, Request, Response

from findme.albums import delete_album, delete_user, load_meta, require_owner, set_venue
from findme.errors import ApiError

router = APIRouter()


@router.delete("/users/{user_id}", status_code=204)
async def remove_user(user_id: str, request: Request):
    delete_user(request.app.state.root, user_id)
    return Response(status_code=204)


@router.delete("/albums/{album_id}", status_code=204)
async def remove_album(
    album_id: str, request: Request, x_owner_token: str | None = Header(default=None)
):
    delete_album(request.app.state.root, album_id, x_owner_token)
    return Response(status_code=204)


@router.patch("/albums/{album_id}/venue")
async def link_venue(album_id: str, request: Request, x_owner_token: str | None = Header(default=None)):
    body = await request.json()
    venue = body.get("venue")
    if not venue or not all(k in venue for k in ("label", "lat", "lon")):
        raise ApiError("UNSUPPORTED_MEDIA", "venue requires label, lat, lon.")
    venue["source"] = "user"
    meta = set_venue(request.app.state.root, album_id, x_owner_token, venue)
    return {"venue": meta["venue"]}


@router.delete("/albums/{album_id}/venue", status_code=204)
async def unlink_venue(album_id: str, request: Request, x_owner_token: str | None = Header(default=None)):
    set_venue(request.app.state.root, album_id, x_owner_token, None)
    return Response(status_code=204)
