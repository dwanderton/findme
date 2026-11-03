# findMe

Upload an album, enroll a selfie, get back every photo you appear in. Each
match carries where it was taken (Google Geocoding), the weather at capture
time (Open-Meteo), the camera settings that shot it (EXIF), and a generated
caption, tags, and story (Qwen2.5-VL on Runpod).

Face detection (SCRFD) and embedding (ArcFace, 512-D) run on Runpod serverless
RTX 4090 workers, scale-to-zero. Matching uses a reference set per user
(1 selfie required, up to 5) with bootstrap re-scoring: confident hits become
extra references and everything re-scores by mean of top-3 similarities.
Bands: strong at 0.45 cosine, possible at 0.37.

## Run locally (no cloud, no keys)

```bash
cd backend
uv venv --python 3.13 && uv pip install -e ".[dev]"
FINDME_STORAGE_ROOT=/tmp/findme FINDME_INLINE_JOBS=true DEBUG_UI=true \
  .venv/bin/python -m uvicorn --factory findme.app.factory:create_app --port 8000
```

```bash
cd frontend
npm install && npm run dev   # http://localhost:3000
```

The face engine runs on CPU locally (same models, same math as the GPU
workers). Without a Google key, enrichment degrades honestly to
"metadata scrubbed" / "lookup failed" states; that degradation is part of the
product, not a crash.

## Tests

```bash
cd backend && .venv/bin/pytest            # 135: unit, routes, golden pipeline, integration
cd frontend && npm test                   # 63: logic, state machines, voice lint
cd frontend && npx playwright test        # 2: live-stack core pathway
python scripts/smoke.py --expect-degraded # full workflow against a running backend
```

Golden accuracy tests run the real ONNX models on CPU: the two crowd-photo
assets share attendees that must cross-match at >= 0.90 cosine.

## Architecture

```
browser  — client preprocess: EXIF out (exifr) -> 2048px resize -> batched upload
   |
next.js proxy (vercel) — rate buckets, error envelope, SSE relay, x-request-id
   |
runpod serverless (US-IL-1, flash)
   /upload /enroll /find /status /debug (LB) · index CPU->GPU (QB) · vlm (QB, worker-vllm)
   |
network volume — photos, thumbs, parquet face shards, enrichment cluster cache,
                 vlm records, per-writer trace files
   |
external (server-side only) — Google Geocoding + Places · Open-Meteo
```

Key decisions and their verification live in `plans/` (gitignored working
docs): the enrichment failure ladder, spatiotemporal cluster cache (place
reused within a quarter mile, weather within a mile and 30 minutes), the
match-only external-call invariant, and the live-tested finding that Runpod's
S3 API lacks CORS (hence the upload endpoint owns ingest).

## Deploy

See [DEPLOY.md](DEPLOY.md). Needs `RUNPOD_API_KEY` and `GOOGLE_MAPS_API_KEY`;
Vercel hosts the frontend. Standing cost when idle: the 20 GB volume
($1.40/mo); all compute is flex min=0.

## Honest limitations

- Find-grants and rate buckets are in-memory per worker (fine at this scale;
  volume-backed grants are the production fix).
- Album photos are stored as 2048 px processed copies; downloads say so.
- InsightFace model licenses are research/non-commercial.
- Full audit: [AUDIT.md](AUDIT.md).
