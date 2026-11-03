import { describe, expect, it } from "vitest";

import { EtaTracker, shouldDowngrade, stageViews } from "../progressClient";

describe("EtaTracker gates", () => {
  it("not confident before ten seconds of samples", () => {
    const t = new EtaTracker();
    t.observe(0, 0);
    t.observe(5_000, 50);
    expect(t.compute(5_000, 50, 100).confident).toBe(false);
  });

  it("not confident below ten percent", () => {
    const t = new EtaTracker();
    for (let s = 0; s <= 15; s++) t.observe(s * 1000, s * 0.5);
    expect(t.compute(15_000, 7, 100).confident).toBe(false);
  });

  it("confident at constant rate with sane eta on 5s grid", () => {
    const t = new EtaTracker();
    for (let s = 0; s <= 15; s++) t.observe(s * 1000, s * 10);
    const r = t.compute(15_000, 150, 300);
    expect(r.confident).toBe(true);
    expect(Math.abs(r.etaSec! - 15)).toBeLessThanOrEqual(5);
    expect(r.etaSec! % 5).toBe(0);
  });
});

describe("stageViews", () => {
  it("marks done/active/todo around the current stage", () => {
    const v = stageViews("embedding", {});
    expect(v.map((x) => x.state)).toEqual(["done", "done", "active", "todo"]);
  });

  it("ready marks everything done", () => {
    const v = stageViews("ready", {});
    expect(v.every((x) => x.state === "done")).toBe(true);
  });

  it("failed marks failed", () => {
    expect(stageViews("failed", {}).every((x) => x.state === "failed")).toBe(true);
  });
});

describe("downgrade", () => {
  it("after two sse failures", () => {
    expect(shouldDowngrade(1)).toBe(false);
    expect(shouldDowngrade(2)).toBe(true);
  });
});
