import json

import httpx
import pytest
import respx

from findme.vlm import VlmClient
from tests.fixtures import jpeg

BASE = "http://vlm.test"
CHAT = f"{BASE}/v1/chat/completions"


def chat_reply(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


@pytest.fixture
def vlm(tmp_path):
    return VlmClient(tmp_path, "a1", base_url=BASE, model="test-model")


@respx.mock
async def test_caption_taxonomy_enforced(vlm):
    body = json.dumps(
        {"caption": "You on stage.", "tags": ["stage", "flying-unicorn", "indoors"], "altText": "Speaker on stage."}
    )
    respx.post(CHAT).respond(json=chat_reply(body))
    async with httpx.AsyncClient() as c:
        r = await vlm.caption_photo(c, "p1", jpeg())
    assert r["status"] == "ready"
    assert r["tags"] == ["stage", "indoors"]


@respx.mock
async def test_caption_cached_create_only(vlm):
    body = json.dumps({"caption": "First.", "tags": ["candid"], "altText": "x"})
    route = respx.post(CHAT).respond(json=chat_reply(body))
    async with httpx.AsyncClient() as c:
        r1 = await vlm.caption_photo(c, "p1", jpeg())
        r2 = await vlm.caption_photo(c, "p1", jpeg())
    assert r1["caption"] == r2["caption"] == "First."
    assert route.call_count == 1


@respx.mock
async def test_endpoint_down_unavailable(vlm):
    respx.post(CHAT).respond(status_code=503)
    async with httpx.AsyncClient() as c:
        r = await vlm.caption_photo(c, "p1", jpeg())
    assert r["status"] == "unavailable"
    assert vlm.cached("p1") is None


async def test_no_base_url_unavailable(tmp_path):
    v = VlmClient(tmp_path, "a1", base_url="")
    async with httpx.AsyncClient() as c:
        r = await v.caption_photo(c, "p1", jpeg())
        s = await v.story(c, ["p1"], [])
    assert r["status"] == "unavailable" and s["status"] == "unavailable"


@respx.mock
async def test_garbage_reply_unavailable(vlm):
    respx.post(CHAT).respond(json=chat_reply("I cannot help with that."))
    async with httpx.AsyncClient() as c:
        r = await vlm.caption_photo(c, "p1", jpeg())
    assert r["status"] == "unavailable"


@respx.mock
async def test_story_cached_by_result_set(vlm):
    route = respx.post(CHAT).respond(json=chat_reply("A sunny afternoon at Shoreline."))
    async with httpx.AsyncClient() as c:
        s1 = await vlm.story(c, ["p2", "p1"], [{"place": "Shoreline"}])
        s2 = await vlm.story(c, ["p1", "p2"], [{"place": "Shoreline"}])
    assert s1["status"] == "ready" and s1["text"] == s2["text"]
    assert route.call_count == 1
