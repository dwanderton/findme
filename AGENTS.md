# AGENTS.md — deploy findMe from this repo

You are an agent. Follow these steps in order. Each step has a verification;
do not advance past a failed verification. No step is optional unless marked.

Human-oriented context lives in [DEPLOY.md](DEPLOY.md). This file is the
executable path.

## What you are deploying

- `findme-api`: Runpod serverless **load-balancer** endpoint, GPU. FastAPI
  image, `FINDME_INLINE_JOBS=true`. Face detection + embedding + matching
  in-process.
- `findme-vlm`: Runpod serverless **queue** endpoint. `runpod/worker-v1-vllm`
  serving Qwen2.5-VL-7B-AWQ captions.
- Frontend: Next.js on Vercel. Proxies every browser request to the api
  endpoint with server-side auth.

## Required inputs

Stop and ask the user if any of these is missing. Do not invent them.

| Input | Shape |
|-------|-------|
| `RUNPOD_API_KEY` | `rpa_...`, read + write |
| `GOOGLE_MAPS_API_KEY` | Geocoding API + Places API (New) + Maps Static API enabled, billing on |
| GitHub PAT | `write:packages` scope, for ghcr.io push |
| Docker with buildx | linux/amd64 build |
| `vercel` CLI, logged in | `vercel whoami` prints a user |

## Step 1 — clone and fetch model weights

```bash
git clone https://github.com/dwanderton/findme && cd findme
curl -L -o /tmp/buffalo_l.zip \
  https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip
unzip -j /tmp/buffalo_l.zip "*det_10g.onnx" "*w600k_r50.onnx" -d assets/
```

Verify: `ls -la assets/det_10g.onnx assets/w600k_r50.onnx` — both exist,
w600k_r50 is ~174 MB. The `.onnx` files are gitignored; the Dockerfile COPYs
them from `assets/`.

## Step 2 — run the test suites

```bash
cd backend && uv venv --python 3.13 && uv pip install -e ".[dev]" && .venv/bin/pytest -q
cd ../frontend && npm install && npm test && npm run build
cd ..
```

Verify: both suites pass, build clean. A failing clone is not deployable;
stop and report.

## Step 3 — build and push the api image

Repo root is the build context. Versioned tag, never `:latest`.

```bash
docker login ghcr.io -u <github-user>     # password = the PAT
docker buildx build --platform linux/amd64 \
  -f backend/Dockerfile \
  -t ghcr.io/<github-user>/findme/api:v1 --push .
```

Verify: push prints a sha256 digest.

## Step 4 — Runpod account resources

Use the Runpod MCP tools (`create-secret`, `create-registry`,
`create-network-volume`) or the console with the same values.

1. Secret `findme-google-maps-api-key` = the Google key.
2. Secret `findme-runpod-api-key` = the Runpod key.
3. Registry credential: ghcr.io, GitHub username + PAT (needed if the ghcr
   package is private).
4. Network volume: name `findme`, 20 GB, data center **US-NE-1**.

Verify: `list-secrets` shows both, `list-network-volumes` shows the volume
with the US-NE-1 data center id.

## Step 5 — VLM endpoint (create this FIRST; the api needs its id)

`create-endpoint`, type QUEUE:

| Field | Value |
|-------|-------|
| name | `findme-vlm` |
| image | `runpod/worker-v1-vllm:v2.25.0` |
| dataCenterIds | `["US-NE-1"]` |
| gpu | count 1, pools `AMPERE_24, ADA_48_PRO, BLACKWELL_96`, minCudaVersion `12.8` |
| workers | min 0, max 1, idleTimeout 1800 |
| scaling | QUEUE_DELAY, 4 s |
| flashboot | on |
| disk | 40 GB |
| networkVolumes | the `findme` volume id |
| env | `MODEL_NAME=Qwen/Qwen2.5-VL-7B-Instruct-AWQ`, `MAX_MODEL_LEN=8192`, `HF_HOME=/runpod-volume/hf-cache` |

Record the endpoint id as `<vlm-id>`. First cold start downloads ~6 GB of
weights to the volume (minutes, one time).

## Step 6 — api endpoint

`create-endpoint`, type LOAD_BALANCER:

| Field | Value |
|-------|-------|
| name | `findme-api` |
| image | `ghcr.io/<github-user>/findme/api:v1` + the registry credential id |
| dataCenterIds | `["US-NE-1"]` |
| gpu | count 1, pools `AMPERE_24, ADA_24, ADA_48_PRO, BLACKWELL_96`, minCudaVersion `12.8` |
| workers | min 0, max 2, idleTimeout 1800 |
| scaling | REQUEST_COUNT, 4 |
| flashboot | on |
| disk | 20 GB |
| ports | `80/http, 8000/http` |
| networkVolumes | the `findme` volume id |

Env block:

```
PORT=8000
PORT_HEALTH=8000
GOOGLE_MAPS_API_KEY={{ RUNPOD_SECRET_findme-google-maps-api-key }}
RUNPOD_API_KEY={{ RUNPOD_SECRET_findme-runpod-api-key }}
VLM_BASE_URL=https://api.runpod.ai/v2/<vlm-id>/openai
VLM_MODEL=Qwen/Qwen2.5-VL-7B-Instruct-AWQ
CORS_ORIGINS=placeholder-until-step-7
DEBUG_UI=true
```

Record the endpoint id as `<api-id>`. Verify (cold start 10-30 s is normal;
retry up to 6 times, 15 s apart):

```bash
curl -H "Authorization: Bearer $RUNPOD_API_KEY" \
  https://<api-id>.api.runpod.ai/ping
# -> {"status":"ok"}
```

Every request to the LB gateway needs that Bearer header. 401 "no token
provided" means you forgot it, not that the worker is broken.

## Step 7 — frontend on Vercel

```bash
cd frontend
vercel env add BACKEND_URL production      # https://<api-id>.api.runpod.ai
vercel env add RUNPOD_API_KEY production   # the key
vercel env add VLM_BASE_URL production     # https://api.runpod.ai/v2/<vlm-id>/openai
vercel deploy --prod --yes
```

Record the production URL as `<frontend-url>`. Then set
`CORS_ORIGINS=<frontend-url>` on the api endpoint with `update-endpoint`
and apply it with the forced rollout (step 8) — env edits only roll as
workers cycle.

## Step 8 — forced rollout (every image or env change, always)

Runpod has no immediate-rollout flag. Stale workers keep serving the old
release indefinitely under traffic. Procedure:

1. `update-endpoint <api-id>` with the new image/env AND
   `{"workers": {"min": 0, "max": 0}}` — terminates everything, pauses the
   endpoint.
2. Poll `list-endpoint-workers <api-id>` until `summary.total` = 0.
3. `update-endpoint <api-id>` `{"workers": {"min": 0, "max": 2, "idleTimeout": 1800}}`.
4. First request after unpause may 409 ENDPOINT_PAUSED; gateway lag is
   ~20-25 s. Retry, then verify against a route or env value that only
   exists in the new release.

## Step 9 — verification gates

All four must pass before you report success:

```bash
RUNPOD_API_KEY=... python scripts/smoke.py --base https://<api-id>.api.runpod.ai
```

1. Smoke twice: cold then warm. Full workflow (album, upload, index, enroll,
   find, download, delete) green both runs.
2. `GET https://<frontend-url>/api/staticmap?lat=37.4267&lon=-122.0806&zoom=14`
   returns `200 image/png` — proves the proxy, auth, and Google key.
3. `POST https://<frontend-url>/api/warmup` returns `{"status":"warming","api":true,"vlm":true}`
   (or `already-warm` within 60 s of a previous call).
4. Debug console (backtick on the album page, `DEBUG_UI=true`) shows
   `provider: CUDAExecutionProvider` in the index trace — CPU fallback there
   means the GPU libs did not load; rebuild, do not ship.

## Cost shape

Idle cost is the volume only (20 GB, $1.40/mo). Compute is flex min=0.
Idle timeouts are 1800 s on both endpoints: a warmed worker bills up to
30 min after its last request, then scales to zero.
