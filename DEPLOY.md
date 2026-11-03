# Deploy runbook

Live shape: two Runpod serverless endpoints in US-NE-1 plus the Next.js
frontend on Vercel.

- `findme-api`: load-balancer endpoint, GPU, running the FastAPI image
  (`ghcr.io/dwanderton/findme/api:vN`) with `FINDME_INLINE_JOBS=true`, so
  detection, embedding, and matching all run in-process on the LB worker.
- `findme-vlm`: queue endpoint running Runpod's vLLM worker with
  Qwen2.5-VL-7B-AWQ; the api endpoint calls it through the OpenAI-compatible
  gateway.

Local dev needs none of this: `FINDME_INLINE_JOBS=true uvicorn --factory
findme.app.factory:create_app` + `npm run dev` (see README).

## Prerequisites

| Credential / tool | Used for |
|------------------|----------|
| `RUNPOD_API_KEY` (read & write) | creating resources; Vercel proxy auth; api workers calling the VLM gateway |
| `GOOGLE_MAPS_API_KEY` with **Geocoding API**, **Places API (New)**, **Maps Static API** enabled, billing attached | place + weather enrichment, venue autocomplete, map cards |
| GitHub PAT with `write:packages` | pushing the image to ghcr.io |
| Docker with buildx | linux/amd64 image build from a Mac |
| `vercel` CLI, logged in | frontend deploy |

**Model weights (fresh clone):** `backend/Dockerfile` COPYs
`assets/det_10g.onnx` and `assets/w600k_r50.onnx` (SCRFD detector + ArcFace
embedder from insightface's buffalo_l pack). The `.onnx` files are gitignored
(w600k_r50 is 174 MB), so on a fresh clone download
<https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip>
and place those two files in `assets/` before building. The crowd fixtures
`assets/s2_a.jpg` / `s2_b.jpg` (used by the smoke script, golden tests, and
Playwright e2e) are committed.

## 1. Build and push the image

From the repo root (the Dockerfile needs repo-root build context):

```bash
docker login ghcr.io -u <github-user>   # password = the PAT
docker buildx build --platform linux/amd64 \
  -f backend/Dockerfile \
  -t ghcr.io/<github-user>/findme/api:v1 --push .
```

Always push a fresh versioned tag, never `:latest` (see Image rollout below).
Make the ghcr package private or public as you prefer; private needs the
registry credential in step 2.

## 2. Runpod resources

Console paths given; every step also works through the Runpod MCP tools /
REST v2 (`create-secret`, `create-registry`, `create-network-volume`,
`create-endpoint`). Order matters: the api endpoint's `VLM_BASE_URL` needs
the VLM endpoint's id, so create the VLM first.

1. **Secrets** (Settings > Secrets):
   - `findme-google-maps-api-key` = the Google key
   - `findme-runpod-api-key` = the Runpod key
2. **Registry credential** (Settings > Container Registry Auth): ghcr.io,
   GitHub username + PAT. Needed for a private ghcr image.
3. **Network volume**: name `findme`, 20 GB, **US-NE-1**. Mounts at
   `/runpod-volume` on both endpoints; holds the VLM's HF weight cache.
4. **VLM endpoint** `findme-vlm` (New Endpoint > Queue):

   | Setting | Value |
   |---------|-------|
   | Image | `runpod/worker-v1-vllm:v2.25.0` |
   | Data center | US-NE-1 (same as the volume) |
   | GPU | 1x, pools AMPERE_24 / ADA_48_PRO / BLACKWELL_96, CUDA >= 12.8 |
   | Workers | min 0, max 1, idle timeout 1800 s, FlashBoot on |
   | Scaling | queue delay 4 s |
   | Container disk | 40 GB |
   | Volume | `findme` |
   | Env | `MODEL_NAME=Qwen/Qwen2.5-VL-7B-Instruct-AWQ`, `MAX_MODEL_LEN=8192`, `HF_HOME=/runpod-volume/hf-cache` |

5. **API endpoint** `findme-api` (New Endpoint > Load Balancer):

   | Setting | Value |
   |---------|-------|
   | Image | `ghcr.io/<github-user>/findme/api:vN` + registry credential |
   | Data center | US-NE-1 |
   | GPU | 1x, pools AMPERE_24 / ADA_24 / ADA_48_PRO / BLACKWELL_96, CUDA >= 12.8 |
   | Workers | min 0, max 2, idle timeout 1800 s, FlashBoot on |
   | Scaling | request count 4 |
   | Container disk | 20 GB |
   | Ports | 80/http, 8000/http |
   | Volume | `findme` |
   | Env | see below |

   ```
   PORT=8000
   PORT_HEALTH=8000
   GOOGLE_MAPS_API_KEY={{ RUNPOD_SECRET_findme-google-maps-api-key }}
   RUNPOD_API_KEY={{ RUNPOD_SECRET_findme-runpod-api-key }}
   VLM_BASE_URL=https://api.runpod.ai/v2/<vlm-endpoint-id>/openai
   VLM_MODEL=Qwen/Qwen2.5-VL-7B-Instruct-AWQ
   CORS_ORIGINS=<frontend origin, set after step 3>
   DEBUG_UI=true
   ```

Sanity check (expect 10-30 s on a cold start, sub-second warm):

```bash
curl -H "Authorization: Bearer $RUNPOD_API_KEY" \
  https://<api-endpoint-id>.api.runpod.ai/ping   # {"status":"ok"}
```

First VLM cold start downloads ~6 GB of weights into the volume's HF cache
(minutes); every later cold start reads the cache.

## 3. Frontend (Vercel)

```bash
cd frontend && vercel deploy --prod
```

Vercel env (server-side only): `BACKEND_URL=https://<api-endpoint-id>.api.runpod.ai`
and `RUNPOD_API_KEY` (used by the `/api` proxy), plus optionally
`VLM_BASE_URL` (same value as on the api endpoint). When set, the landing
page's `/api/warmup` route also warms the VLM endpoint with a one-token
async job; without it only the api endpoint is warmed. Warmup is throttled
to one upstream hit per 60 s per instance; note each VLM warm bills GPU
seconds until its 1800 s idle timeout.

Then set `CORS_ORIGINS` on `findme-api` to the Vercel URL. Env edits cut a
release that only rolls as workers cycle; use the forced rollout below to
apply immediately.

## 4. Verification gates

- `python scripts/smoke.py --base https://<api-endpoint-id>.api.runpod.ai`
  twice: cold + warm (full workflow; records cold start + throughput; needs
  `RUNPOD_API_KEY` in env and the fixtures from Prerequisites).
- Trace line `provider: CUDAExecutionProvider` in the debug console
  (`DEBUG_UI=true`) proves the GPU execution provider loaded.
- Upload a >8 MB-batch album from the browser.
- Forced-failure demo: point the api at a bad Google key, then
  `scripts/smoke.py --expect-degraded` stays green (enrichment degrades,
  never 500s).

## Image rollout (always forced)

Runpod has no immediate-rollout flag: a container change cuts a release that
rolls only as workers cycle, and a stale worker keeps serving the old image
(retries reset its idle timer, so it can stick around indefinitely). The
docs' "strict version consistency" procedure is the default here for every
image update on the api endpoint:

1. Push a new versioned tag (never `:latest`): `ghcr.io/<github-user>/findme/api:vN`.
2. `update-endpoint` with the new image.
3. `update-endpoint {"workers": {"min": 0, "max": 0}}`. Terminates all
   workers including stale ones and PAUSES the endpoint.
4. Poll `list-endpoint-workers` until total = 0 (usually seconds).
5. `update-endpoint {"workers": {"min": 0, "max": 2, "idleTimeout": 1800}}`.
6. Expect ~20-25 s gateway lag after unpause (first request may 409
   ENDPOINT_PAUSED); verify with an authed request to a route that only
   exists in the new image.

Measured 2026-11-02 (v4 to v5): drain instant, first post-restore request
returned 200 in one attempt.

## Cost notes

Flex min=0 everywhere: $0 idle. Standing cost = 20 GB volume ($1.40/mo).
Demo-day warm worker optional: set min=1 on findme-api for the hour, turn it
back to 0 after (checklist, not infra).

## Live resource map (deployed 2026-11-03)

| Resource | ID / URL |
|----------|----------|
| API endpoint (LB, GPU) | `fyn95actlrze1c` -> https://fyn95actlrze1c.api.runpod.ai (gateway requires `Authorization: Bearer RUNPOD_API_KEY`) |
| VLM endpoint (queue, worker-v1-vllm v2.25.0, Qwen2.5-VL-7B-AWQ) | `qqdg8tztrj83bm` -> `VLM_BASE_URL` https://api.runpod.ai/v2/qqdg8tztrj83bm/openai |
| Volume (US-NE-1, 20 GB) | `n8eck87ef2` (mounts `/runpod-volume`; VLM HF cache at `/runpod-volume/hf-cache`) |
| Secrets | `findme-google-maps-api-key`, `findme-runpod-api-key` |
| Registry credential (ghcr) | `cmw01ek13007vydkiux2k0l2s` |
| Image | `ghcr.io/dwanderton/findme/api:v9` |
| Frontend | https://findme-mocha.vercel.app (Vercel project "findme"; env `BACKEND_URL` + `RUNPOD_API_KEY` + `VLM_BASE_URL`) |
