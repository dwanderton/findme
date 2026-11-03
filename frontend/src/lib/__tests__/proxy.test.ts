import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { forward, limitKind } from "../proxy";
import { LIMITS, resetBuckets, take } from "../ratelimit";

describe("ratelimit", () => {
  beforeEach(resetBuckets);

  it("allows within budget then 429s", () => {
    const now = 1_000_000;
    for (let i = 0; i < LIMITS.default.perMin; i++) {
      expect(take("1.2.3.4", "default", now).ok).toBe(true);
    }
    const blocked = take("1.2.3.4", "default", now);
    expect(blocked.ok).toBe(false);
    expect(blocked.retryAfterS).toBeGreaterThan(0);
  });

  it("enroll bucket tighter and independent", () => {
    const now = 1_000_000;
    for (let i = 0; i < LIMITS.enroll.perMin; i++) {
      expect(take("1.2.3.4", "enroll", now).ok).toBe(true);
    }
    expect(take("1.2.3.4", "enroll", now).ok).toBe(false);
    expect(take("1.2.3.4", "default", now).ok).toBe(true);
  });

  it("refills over time", () => {
    const t0 = 1_000_000;
    for (let i = 0; i < LIMITS.enroll.perMin; i++) take("ip", "enroll", t0);
    expect(take("ip", "enroll", t0).ok).toBe(false);
    expect(take("ip", "enroll", t0 + 61_000).ok).toBe(true);
  });

  it("limitKind maps enroll paths", () => {
    expect(limitKind("enroll")).toBe("enroll");
    expect(limitKind("albums/x/status")).toBe("default");
  });
});

describe("forward", () => {
  beforeEach(() => {
    resetBuckets();
    process.env.BACKEND_URL = "http://backend.test";
  });
  afterEach(() => vi.restoreAllMocks());

  it("forwards path, query, owner token; passes envelope through", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "UNKNOWN_ALBUM", message: "x", retryable: false } }), {
        status: 404,
        headers: { "content-type": "application/json" },
      }),
    );
    const req = new Request("http://app.test/api/albums/a1/status?x=1", {
      headers: { "x-owner-token": "tok", "x-forwarded-for": "9.9.9.9" },
    });
    const resp = await forward(req, "albums/a1/status");
    expect(spy).toHaveBeenCalledOnce();
    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://backend.test/albums/a1/status?x=1");
    expect(new Headers(init.headers).get("x-owner-token")).toBe("tok");
    expect(resp.status).toBe(404);
    const body = await resp.json();
    expect(body.error.code).toBe("UNKNOWN_ALBUM");
  });

  it("backend down maps to 502 envelope", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("refused"));
    const resp = await forward(new Request("http://app.test/api/find"), "find");
    expect(resp.status).toBe(502);
    const body = await resp.json();
    expect(body.error.retryable).toBe(true);
  });

  it("rate limited requests never reach backend", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    const mk = () => new Request("http://app.test/api/enroll", { method: "POST", headers: { "x-forwarded-for": "7.7.7.7" } });
    for (let i = 0; i < LIMITS.enroll.perMin; i++) await forward(mk(), "enroll");
    const blocked = await forward(mk(), "enroll");
    expect(blocked.status).toBe(429);
    expect(blocked.headers.get("retry-after")).toBeTruthy();
    expect(spy).toHaveBeenCalledTimes(LIMITS.enroll.perMin);
  });
});
