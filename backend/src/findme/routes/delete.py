from __future__ import annotations

from fastapi import APIRouter, Header, Request, Response

from datetime import datetime

from findme.albums import delete_album, delete_user, load_meta, require_owner, set_photo_timestamp, set_venue
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


# PUT alongside PATCH: some Runpod LB gateways drop PATCH before it reaches the worker.
@router.api_route("/albums/{album_id}/venue", methods=["PATCH", "PUT"])
async def link_venue(album_id: str, request: Request, x_owner_token: str | None = Header(default=None)):
    body = await request.json()
    venue = body.get("venue")
    if not venue and body.get("placeId"):
        import httpx

        from findme.places import details
        from findme.trace import writer_for

        trace = writer_for(request.app.state.root, album_id, "places")
        rid = request.headers.get("x-request-id", "")
        async with httpx.AsyncClient() as client:
            venue = await details(client, body["placeId"], body.get("session", "no-session"), trace=trace, request_id=rid)
        if venue is None:
            raise ApiError("UPSTREAM_MAPS", "Place lookup failed; retry.")
    if not venue or not all(k in venue for k in ("label", "lat", "lon")):
        raise ApiError("UNSUPPORTED_MEDIA", "venue requires placeId or label, lat, lon.")
    venue["source"] = "user"
    meta = set_venue(request.app.state.root, album_id, x_owner_token, venue)
    return {"venue": meta["venue"]}


@router.api_route("/albums/{album_id}/photos/{photo_id}/timestamp", methods=["PATCH", "PUT"])
async def set_timestamp(
    album_id: str, photo_id: str, request: Request, x_owner_token: str | None = Header(default=None)
):
    body = await request.json()
    taken_at = str(body.get("takenAt", "")).strip()
    try:
        datetime.fromisoformat(taken_at)
    except ValueError:
        raise ApiError("UNSUPPORTED_MEDIA", "takenAt must be an ISO 8601 datetime.")
    info = set_photo_timestamp(request.app.state.root, album_id, x_owner_token, photo_id, taken_at)
    return {"photoId": photo_id, "takenAt": info["exif"]["taken_at"]}


@router.delete("/albums/{album_id}/venue", status_code=204)
async def unlink_venue(album_id: str, request: Request, x_owner_token: str | None = Header(default=None)):
    set_venue(request.app.state.root, album_id, x_owner_token, None)
    return Response(status_code=204)
