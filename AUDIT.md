# Production-readiness audit (2026-11-02)

## Test inventory

| Suite | Count | Runtime |
|-------|-------|---------|
| Backend unit + routes | 129 | ~16 s |
| Backend integration (real CPU face engine, fixture album) | 6 | ~6 s |
| Frontend unit (vitest) | 63 | <1 s |
| Playwright e2e (live local stack) | 2 | ~7 s |
| Smoke script (full pathway, degradation asserted) | 1 run | ~7 s |

## Security checklist — walked

- Keys server-side: GOOGLE_MAPS_API_KEY read only in backend modules (`geo.py`,
  `places.py`); RUNPOD_API_KEY attached only in the Next server proxy. Grep of
  the client bundle inputs shows neither. git history greps clean of key
  patterns.
- Validation: magic-byte sniff, 50 MP decode guard, selfie 1-5 caps, batch
  caps, UUID capability model, X-Owner-Token on venue/delete — all test-covered.
- Rate limits: per-IP buckets (120/min default, 5/min enroll, 10/min places),
  429 + Retry-After before upstream is touched.
- Upstream failure ladder: cluster cache, 3 s timeouts, retry x2 with
  Retry-After override, independent 60 s circuits, 50-call budget, degradation
  statuses — all table-driven test covered.
- Debug endpoint: DEBUG_UI-gated, redaction-at-write verified by test
  (secrets absent from raw trace files).
- Delete: erases album tree + enrich cache + vectors; verified by 404 re-read.

## Known weaknesses (disclosed, not hidden)

- Find-grants and rate-limit buckets are in-memory per worker instance. With
  multiple LB workers a photo request can land on a worker that did not serve
  the find. Acceptable at take-home scale (workers 0-2, sticky in practice);
  the volume-backed grant file is the production fix.
- Owner token lives in localStorage; XSS in the app would expose it. No
  third-party scripts are loaded, mitigating exposure.
- VLM taxonomy enforcement is server-side, but prompt-injection via EXIF
  fields into the story prompt is conceivable; records are truncated at 6000
  chars and tags filtered to the fixed list.

## Design re-audit vs rendered UI

- Dark-first OKLCH tokens, purple as anchor only (CTA, focus, active chips):
  pass.
- Status always token + text (band chips, stage dots with labels): pass.
- Numbers mono + tabular (scores 2dp raw, counts, percentages): pass.
- Motion is state only: pulse on active stage, log-stream on arrivals,
  card-in stagger, backdrop fill = upload progress; reduced-motion kills all:
  pass.
- No spinners: staged pipeline + skeleton copy: pass.
- No fabricated numbers: ETA gated by confidence, cold-start countdown
  server-driven: pass.

## Voice rule 8 — executable

`copy.test.ts` lints every user-facing string against the banned list
(em dashes, tell-tale words, emoji, RunPod misspelling) in CI. Source greps
across tsx/ts: zero violations outside the lint definitions themselves.

## Outstanding for production sign-off

Live deploy pending two credentials (see DEPLOY.md): RUNPOD_API_KEY,
GOOGLE_MAPS_API_KEY. The deployed smoke run (cold start, GPU provider line,
throughput) completes the final gates.

## Addendum (2026-11-02, post-polish pass)

- Deps: TypeScript 7.0.2 (major, clean), python-dateutil 4.x; everything else
  already latest. npm audit: 3 moderate (minimatch DoS) confined to
  openapi-typescript's dev-only chain; no runtime exposure; npm's forced fix
  would downgrade a major, declined. Revisit when @redocly/openapi-core bumps.
- Social surface: icon.svg + apple-icon.png + dynamic OG image (next/og,
  verified 200 image/png), metadataBase, twitter card.
- Design re-audit after UX changes: progress now a single current-stage line
  with pulsing running dot (motion-as-state, exactly one visible status);
  upload dropzone unmounts at commit (no dead UI); backdrop raised to
  visible contrast while keeping content legible under the gradient. Voice
  lint still green; no em dashes or emoji in shipped strings.
