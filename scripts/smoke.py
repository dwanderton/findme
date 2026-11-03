#!/usr/bin/env python3
"""findMe smoke test.

Dry mode (default): drives the full workflow against a local backend
(http://localhost:8000) with the real CPU face engine.

Live mode (--base <url>): same flow against a deployed stack; records
observed cold start and throughput as log lines for the plans decisions log.

Forced-failure check: with --expect-degraded, asserts enrichment degrades
(partial/upstream-failed/scrubbed) rather than 500ing when Google is absent.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from pathlib import Path

import httpx

ASSETS = Path(__file__).resolve().parents[1] / "plans" / "reference" / "assets"


def log(msg: str) -> None:
    print(f"[smoke +{time.time() - T0:6.1f}s] {msg}", flush=True)


T0 = time.time()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--expect-degraded", action="store_true")
    ap.add_argument("--skip-vlm-assert", action="store_true")
    args = ap.parse_args()

    c = httpx.Client(base_url=args.base, timeout=120)

    t = time.time()
    r = c.get("/health")
    r.raise_for_status()
    log(f"health ok ({(time.time() - t) * 1000:.0f} ms, cold start included)")

    album = c.post("/albums", json={"photoCount": 4}).json()
    album_id, owner = album["albumId"], album["ownerToken"]
    log(f"album {album_id[:8]} created")

    crowd_a = (ASSETS / "s2_a.jpg").read_bytes()
    crowd_b = (ASSETS / "s2_b.jpg").read_bytes()
    files = [
        ("p0", ("crowd_a.jpg", crowd_a, "image/jpeg")),
        ("p1", ("crowd_b.jpg", crowd_b, "image/jpeg")),
    ]
    r = c.post("/upload", data={"albumId": album_id}, files=files)
    assert r.json()["stored"] == 2, r.text
    log("uploaded 2 crowd photos")

    t = time.time()
    r = c.post(f"/albums/{album_id}/commit", json={"uploaded": 2})
    assert r.status_code == 202, r.text

    deadline = time.time() + 300
    faces = 0
    while time.time() < deadline:
        s = c.get(f"/albums/{album_id}/status").json()
        if s["stage"] == "ready":
            faces = s["facesFound"]
            break
        if s["stage"] == "failed":
            log(f"FAIL index failed: {s}")
            return 1
        time.sleep(2)
    else:
        log("FAIL index timed out")
        return 1
    index_s = time.time() - t
    log(f"index ready: {faces} faces in {index_s:.1f}s ({2 / index_s:.1f} photos/s observed)")
    assert faces > 40, f"expected crowd faces, got {faces}"

    t = time.time()
    r = c.post("/enroll", files=[("s0", ("me.jpg", crowd_a, "image/jpeg"))])
    assert r.status_code == 200, r.text
    user_id = r.json()["userId"]
    log(f"enrolled {user_id[:8]} in {time.time() - t:.1f}s")

    t = time.time()
    r = c.get("/find", params={"userId": user_id, "albumId": album_id, "threshold": "possible"})
    assert r.status_code == 200, r.text
    body = r.json()
    log(f"find: {len(body['matches'])} matches in {time.time() - t:.1f}s · enrichment {body['enrichmentSummary']} · vlm {body['vlmSummary']}")
    assert body["matches"], "self-match must appear"

    statuses = {m["enrichment"]["status"] for m in body["matches"]}
    if args.expect_degraded:
        assert statuses <= {"partial", "upstream-failed", "metadata-scrubbed", "deferred"}, statuses
        log(f"degradation verified: {statuses} (no 500s)")

    if not args.skip_vlm_assert:
        vlm_states = {m["vlm"]["status"] for m in body["matches"]}
        log(f"vlm states: {vlm_states}")

    r = c.get(f"/albums/{album_id}/download", params={"userId": user_id})
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip", r.status_code
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert "findme.json" in z.namelist()
    log(f"download ok: {len(z.namelist())} entries, {len(r.content) / 1e6:.1f} MB, X-Parts={r.headers.get('x-parts')}")

    r = c.post("/enroll", files=[("s0", ("me2.jpg", crowd_b, "image/jpeg"))])
    user2 = r.json()["userId"]
    r = c.get("/find", params={"userId": user2, "albumId": album_id, "threshold": "possible"})
    assert r.status_code == 200
    log(f"share-link second user: {len(r.json()['matches'])} matches")

    assert c.delete(f"/albums/{album_id}", headers={"X-Owner-Token": owner}).status_code == 204
    assert c.delete(f"/users/{user_id}").status_code == 204
    assert c.get(f"/albums/{album_id}/status").status_code == 404
    log("delete verified: album 404 after erase")

    log("SMOKE GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
