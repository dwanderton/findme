import { describe, expect, it } from "vitest";

import { OfflineQueue, classify, countdown } from "../errorState";

describe("classify", () => {
  it("rate limited uses retry-after header", () => {
    const e = classify(429, "RATE_LIMITED", "17");
    expect(e.kind).toBe("rate-limited");
    expect(e.retryAfterS).toBe(17);
    expect(e.retryable).toBe(true);
  });

  it("cold start defaults ten seconds", () => {
    const e = classify(503, "COLD_START", null);
    expect(e.kind).toBe("cold-start");
    expect(e.retryAfterS).toBe(10);
  });

  it("validation codes stay inline", () => {
    for (const code of ["NO_FACE_IN_SELFIE", "UNSUPPORTED_MEDIA", "TOO_MANY_SELFIES", "BODY_TOO_LARGE"]) {
      expect(classify(400, code, null).kind).toBe("validation");
    }
  });

  it("offline wins over everything", () => {
    expect(classify(429, "RATE_LIMITED", "5", false).kind).toBe("offline");
  });

  it("status fallbacks without codes", () => {
    expect(classify(429, undefined, null).kind).toBe("rate-limited");
    expect(classify(503, undefined, null).kind).toBe("cold-start");
    expect(classify(502, undefined, null).kind).toBe("upstream");
    expect(classify(418, undefined, null).kind).toBe("unknown");
  });

  it("not-ready maps to quick retry", () => {
    expect(classify(409, "INDEX_NOT_READY", null)).toMatchObject({ kind: "not-ready", retryAfterS: 2 });
  });
});

describe("countdown", () => {
  it("counts to zero and clamps", () => {
    expect(countdown(10, 0)).toBe(10);
    expect(countdown(10, 9.2)).toBe(1);
    expect(countdown(10, 12)).toBe(0);
  });
});

describe("offline queue", () => {
  it("flush runs everything once", () => {
    const q = new OfflineQueue();
    let runs = 0;
    q.enqueue({ run: () => runs++ });
    q.enqueue({ run: () => runs++ });
    expect(q.size).toBe(2);
    expect(q.flush()).toBe(2);
    expect(runs).toBe(2);
    expect(q.size).toBe(0);
    expect(q.flush()).toBe(0);
  });
});
