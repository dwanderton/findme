import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from findme.app.factory import create_app
from findme.jobs.vlm_job import run_vlm_job
from findme.vlm import VlmClient
from tests.test_media import noise_jpeg

BASE = "http://vlm.test"
CHAT = f"{BASE}/v1/chat/completions"


@pytest.fixture
def ctx(tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app)
    album_id = client.post("/albums", json={"photoCount": 2}).json()["albumId"]
    files = [(f"p{i}", (f"{i}.jpg", noise_jpeg(i), "image/jpeg")) for i in range(2)]
    client.post("/upload", data={"albumId": album_id}, files=files)
    from findme.albums import load_meta

    photo_ids = sorted(load_meta(tmp_path, album_id)["photos"])
    return tmp_path, album_id, photo_ids


def caption_reply():
    return {"choices": [{"message": {"content": json.dumps({"caption": "You at the event.", "tags": ["candid"], "altText": "Person at event."})}}]}


@respx.mock
async def test_job_captions_and_story(ctx):
    root, album_id, photo_ids = ctx
    route = respx.post(CHAT)
    route.side_effect = [
        httpx.Response(200, json=caption_reply()),
        httpx.Response(200, json=caption_reply()),
        httpx.Response(200, json={"choices": [{"message": {"content": "Two photos from the event."}}]}),
    ]
    vlm = VlmClient(root, album_id, base_url=BASE)
    r = await run_vlm_job(root, album_id, "user-1", photo_ids, photo_ids, vlm=vlm)
    assert r == {"ready": 2, "unavailable": 0, "story": "ready"}
    assert vlm.cached(photo_ids[0])["caption"] == "You at the event."
    assert vlm.cached_story(photo_ids) == "Two photos from the event."


@respx.mock
async def test_endpoint_down_no_retry_storm(ctx):
    root, album_id, photo_ids = ctx
    route = respx.post(CHAT).respond(status_code=503)
    vlm = VlmClient(root, album_id, base_url=BASE)
    r = await run_vlm_job(root, album_id, "user-1", photo_ids, photo_ids, vlm=vlm)
    assert r["ready"] == 0 and r["story"] == "unavailable"
    assert route.call_count == 1


@respx.mock
async def test_cached_photos_skip_calls(ctx):
    root, album_id, photo_ids = ctx
    route = respx.post(CHAT)
    route.side_effect = [
        httpx.Response(200, json=caption_reply()),
        httpx.Response(200, json=caption_reply()),
        httpx.Response(200, json={"choices": [{"message": {"content": "Story."}}]}),
    ]
    vlm = VlmClient(root, album_id, base_url=BASE)
    await run_vlm_job(root, album_id, "user-1", photo_ids, photo_ids, vlm=vlm)
    calls = route.call_count
    r2 = await run_vlm_job(root, album_id, "user-2", photo_ids, photo_ids, vlm=vlm)
    assert r2["ready"] == 2
    assert route.call_count == calls
