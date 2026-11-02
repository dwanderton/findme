# findMe

Upload an album, enroll a selfie, get back every photo you appear in. Each
match comes enriched with where it was taken, the weather at capture time,
the camera settings that shot it, and a generated caption.

Face detection and embedding run on Runpod serverless GPUs (RTX 4090,
scale-to-zero). Two free external APIs enrich matched photos: Google Maps
Geocoding (GPS to place) and Open-Meteo (GPS + timestamp to weather). A
Qwen2.5-VL endpoint on Runpod writes captions, content tags, alt-text, and a
short story of your matches.

## Layout

| Path | What |
|------|------|
| `backend/` | Python: face engine, matching, enrichment, flash serverless endpoints |
| `frontend/` | Next.js app + API proxy (keys stay server-side) |
| `openapi.yaml` | Contract — source of truth for both sides |
| `scripts/` | Model staging, smoke tests |

## Run

See deploy notes at the bottom of this file once P045 lands. Until then:

```bash
cd backend && uv venv --python 3.13 && uv pip install -e ".[dev]" && pytest
cd frontend && npm install && npm run build
```
