# Deploy runbook

Target shape: flash serverless on Runpod (US-IL-1) + Next.js proxy on Vercel.
Local dev needs none of this: `FINDME_INLINE_JOBS=true uvicorn --factory
findme.app.factory:create_app` + `npm run dev`.

## Credentials needed

| Credential | Where it goes | Status |
|------------|---------------|--------|
| `RUNPOD_API_KEY` | shell env for `flash deploy`; Vercel env for the proxy | MISSING |
| `GOOGLE_MAPS_API_KEY` (Geocoding + Places enabled, billing on) | env at `flash deploy` time (injected to workers) | MISSING |
| Runpod S3 API key (console-only) | shell env for `scripts/stage_models.py` | optional (pod fallback) |
| Vercel login | `vercel whoami` | ok (dwanderton) |

## Order

1. `cd backend && uv venv --python 3.13 && uv pip install -e ".[dev]"`
2. `export RUNPOD_API_KEY=... GOOGLE_MAPS_API_KEY=...`
3. Create volume + endpoints: `python flash_app.py` declares them; deploy with
   `flash deploy` from `backend/` (flash provisions the 20 GB volume in
   US-IL-1 and all five endpoints; see plans/high-level/01 for the shape).
4. Stage models: `python scripts/stage_models.py --volume <id>` (or pod +
   `runpodctl send`). Workers read `FINDME_MODELS_DIR=/runpod-volume/models`.
5. VLM weights: first worker boot downloads Qwen2.5-VL-7B-AWQ to the volume
   (`VLLM_CACHE_ROOT=/runpod-volume/models/vllm_cache`); expect minutes on the
   first cold start only.
6. Frontend: `cd frontend && vercel deploy --prod` with env
   `BACKEND_URL=<findme-api LB url>` and `RUNPOD_API_KEY`.
7. Gates (record observations in plans/high-level/07 log):
   - `python scripts/smoke.py --base <findme-api url>` twice: cold + warm
     (captures cold start + throughput = old gates G-b/G-c/G-d)
   - trace line `provider: CUDAExecutionProvider` in the debug console (G-b)
   - upload a >8 MB-batch album from the browser (G-e)
   - flash CPU endpoint created in US-IL-1 or fold-to-GPU fallback applied (G-g)
8. Forced-failure demo: redeploy api with a bad Google key →
   `scripts/smoke.py --expect-degraded` stays green.

## Cost notes

Flex min=0 everywhere: $0 idle. Standing cost = 20 GB volume ($1.40/mo).
Demo-day warm worker optional: set min=1 on findme-enroll for the hour,
turn it back to 0 after (checklist, not infra).
