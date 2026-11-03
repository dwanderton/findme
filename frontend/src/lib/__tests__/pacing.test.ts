import { describe, expect, it } from "vitest";

import { COUNT_STEP_MS, ProgressPacer, STAGE_DWELL_MS } from "../pacing";

describe("stage dwell", () => {
  it("each stage visible at least one second even when backend skips ahead", () => {
    const p = new ProgressPacer(0);
    p.feed("ready", 6, 6);
    expect(p.tick(0).stage).toBe("received");
    expect(p.tick(STAGE_DWELL_MS - 1).stage).toBe("received");
    expect(p.tick(STAGE_DWELL_MS).stage).toBe("extracting");
    expect(p.tick(STAGE_DWELL_MS * 2 - 1).stage).toBe("extracting");
    expect(p.tick(STAGE_DWELL_MS * 2).stage).toBe("embedding");
    expect(p.tick(STAGE_DWELL_MS * 3).stage).toBe("ready");
  });

  it("does not advance past actual stage", () => {
    const p = new ProgressPacer(0);
    p.feed("extracting", 0, 6);
    expect(p.tick(STAGE_DWELL_MS * 5).stage).toBe("extracting");
    p.feed("embedding", 2, 6);
    expect(p.tick(STAGE_DWELL_MS * 6).stage).toBe("embedding");
  });

  it("failed shows immediately", () => {
    const p = new ProgressPacer(0);
    p.feed("embedding", 2, 6);
    p.feed("failed", 2, 6);
    expect(p.tick(1).stage).toBe("failed");
  });
});

describe("counter pacing", () => {
  it("spends at least 100ms per count up to the target", () => {
    const p = new ProgressPacer(0);
    p.feed("extracting", 0, 6);
    p.tick(STAGE_DWELL_MS);
    p.feed("extracting", 6, 6);
    const t0 = STAGE_DWELL_MS;
    expect(p.tick(t0 + COUNT_STEP_MS).done).toBe(1);
    expect(p.tick(t0 + COUNT_STEP_MS * 3).done).toBe(3);
    expect(p.tick(t0 + COUNT_STEP_MS * 6).done).toBe(6);
    expect(p.tick(t0 + COUNT_STEP_MS * 60).done).toBe(6);
  });

  it("counter never exceeds actual progress", () => {
    const p = new ProgressPacer(0);
    p.feed("extracting", 2, 6);
    p.tick(STAGE_DWELL_MS);
    const v = p.tick(STAGE_DWELL_MS + COUNT_STEP_MS * 50);
    expect(v.done).toBe(2);
  });

  it("skips pacing for albums over fifty photos", () => {
    const p = new ProgressPacer(0);
    p.feed("extracting", 0, 200);
    p.tick(STAGE_DWELL_MS);
    p.feed("extracting", 157, 200);
    expect(p.tick(STAGE_DWELL_MS + 1).done).toBe(157);
  });

  it("counter resets per stage", () => {
    const p = new ProgressPacer(0);
    p.feed("extracting", 6, 6);
    p.tick(STAGE_DWELL_MS);
    expect(p.tick(STAGE_DWELL_MS + COUNT_STEP_MS * 6).done).toBe(6);
    p.feed("embedding", 3, 6);
    const t2 = STAGE_DWELL_MS * 2 + COUNT_STEP_MS * 6;
    const v = p.tick(t2);
    expect(v.stage).toBe("embedding");
    expect(v.done).toBeLessThanOrEqual(3);
  });
});
