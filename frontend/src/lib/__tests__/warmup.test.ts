import { beforeEach, describe, expect, it } from "vitest";

import { claimWarm, resetWarm, vlmRunUrl, WARM_INTERVAL_MS } from "../warmup";

describe("claimWarm", () => {
  beforeEach(() => resetWarm());

  it("first claim wins, repeat within the interval loses", () => {
    expect(claimWarm(1_000)).toBe(true);
    expect(claimWarm(1_000 + WARM_INTERVAL_MS - 1)).toBe(false);
  });

  it("claim succeeds again after the interval", () => {
    expect(claimWarm(1_000)).toBe(true);
    expect(claimWarm(1_000 + WARM_INTERVAL_MS)).toBe(true);
  });
});

describe("vlmRunUrl", () => {
  it("derives /run from the openai base", () => {
    expect(vlmRunUrl("https://api.runpod.ai/v2/qqdg8tztrj83bm/openai")).toBe(
      "https://api.runpod.ai/v2/qqdg8tztrj83bm/run",
    );
  });

  it("tolerates a trailing slash", () => {
    expect(vlmRunUrl("https://api.runpod.ai/v2/abc123/openai/")).toBe("https://api.runpod.ai/v2/abc123/run");
  });

  it("rejects non-runpod or malformed bases", () => {
    expect(vlmRunUrl("https://evil.example.com/v2/abc/openai")).toBeNull();
    expect(vlmRunUrl("http://api.runpod.ai/v2/abc/openai")).toBeNull();
    expect(vlmRunUrl("")).toBeNull();
  });
});
