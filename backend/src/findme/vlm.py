from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import httpx

TAXONOMY = [
    "stage",
    "group",
    "portrait",
    "candid",
    "posed",
    "outdoors",
    "indoors",
    "night",
    "daytime",
    "food",
    "crowd",
    "closeup",
]

CAPTION_PROMPT = (
    "Describe this photo for the person highlighted by the context. Reply as JSON: "
    '{"caption": one short sentence, "tags": up to 4 from this exact list '
    f"{TAXONOMY}, " '"altText": one accessibility sentence}. No other keys.'
)

TIMEOUT_S = 120.0


class VlmClient:
    def __init__(self, root: Path, album_id: str, base_url: str | None = None, model: str | None = None):
        self.dir = root / "vlm"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url or os.environ.get("VLM_BASE_URL", "")
        self.model = model or os.environ.get("VLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct-AWQ")

    def cached(self, photo_id: str) -> dict | None:
        p = self.dir / f"{photo_id}.json"
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                return None
        return None

    def _store(self, photo_id: str, record: dict) -> None:
        p = self.dir / f"{photo_id}.json"
        if p.exists():
            return
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(record))
        tmp.replace(p)

    @staticmethod
    def _parse(content: str) -> dict | None:
        try:
            start = content.index("{")
            end = content.rindex("}") + 1
            obj = json.loads(content[start:end])
        except (ValueError, json.JSONDecodeError):
            return None
        caption = str(obj.get("caption", "")).strip()
        alt = str(obj.get("altText", "")).strip()
        tags = [t for t in obj.get("tags", []) if isinstance(t, str) and t in TAXONOMY][:4]
        if not caption:
            return None
        return {"status": "ready", "caption": caption, "tags": tags, "altText": alt or caption}

    async def _chat(self, client: httpx.AsyncClient, messages: list[dict], max_tokens: int = 300) -> str:
        headers = {}
        key = os.environ.get("RUNPOD_API_KEY", "")
        if key and "runpod.ai" in self.base_url:
            headers["Authorization"] = f"Bearer {key}"
        resp = await client.post(
            f"{self.base_url}/v1/chat/completions",
            json={"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2},
            headers=headers,
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def caption_photo(self, client: httpx.AsyncClient, photo_id: str, image: bytes) -> dict:
        hit = self.cached(photo_id)
        if hit:
            return hit
        if not self.base_url:
            return {"status": "unavailable"}
        b64 = base64.b64encode(image).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": CAPTION_PROMPT},
                ],
            }
        ]
        try:
            content = await self._chat(client, messages)
        except (httpx.HTTPError, KeyError, IndexError):
            return {"status": "unavailable"}
        record = self._parse(content)
        if record is None:
            return {"status": "unavailable"}
        self._store(photo_id, record)
        return record
