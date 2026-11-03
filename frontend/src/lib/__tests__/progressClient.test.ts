import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EtaTracker, shouldDowngrade, stageViews, watchProgress } from "../progressClient";

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

/* happy-dom has no EventSource, so watchProgress takes the polling path —
 * the lifecycle rules under test are transport-independent. */
describe("watchProgress lifecycle", () => {
  const handlers = () => ({ onSnapshot: vi.fn(), onDone: vi.fn(), onFailed: vi.fn() });
  let hidden = false;

  const setHidden = (value: boolean) => {
    hidden = value;
    document.dispatchEvent(new Event("visibilitychange"));
  };

  const respond = (stage: string) =>
    vi.fn(async () => ({ ok: true, json: async () => ({ stage, photosDone: 0, photosTotal: 1 }) }));

  beforeEach(() => {
    vi.useFakeTimers();
    hidden = false;
    Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("does not open a transport while the tab is hidden, resumes when visible", async () => {
    const fetchMock = respond("embedding");
    vi.stubGlobal("fetch", fetchMock);
    hidden = true;
    const stop = watchProgress("a1", handlers());
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetchMock).not.toHaveBeenCalled();
    setHidden(false);
    await vi.advanceTimersByTimeAsync(4_000);
    expect(fetchMock).toHaveBeenCalled();
    stop();
  });

  it("pauses polling when the tab goes hidden", async () => {
    const fetchMock = respond("embedding");
    vi.stubGlobal("fetch", fetchMock);
    const stop = watchProgress("a1", handlers());
    await vi.advanceTimersByTimeAsync(4_000);
    const callsWhileVisible = fetchMock.mock.calls.length;
    expect(callsWhileVisible).toBeGreaterThan(0);
    setHidden(true);
    await vi.advanceTimersByTimeAsync(20_000);
    expect(fetchMock.mock.calls.length).toBe(callsWhileVisible);
    stop();
  });

  it("stops for good on a terminal snapshot, even across visibility changes", async () => {
    const fetchMock = respond("ready");
    vi.stubGlobal("fetch", fetchMock);
    const h = handlers();
    const stop = watchProgress("a1", h);
    await vi.advanceTimersByTimeAsync(2_100);
    expect(h.onDone).toHaveBeenCalledTimes(1);
    const callsAtTerminal = fetchMock.mock.calls.length;
    setHidden(true);
    setHidden(false);
    await vi.advanceTimersByTimeAsync(20_000);
    expect(fetchMock.mock.calls.length).toBe(callsAtTerminal);
    stop();
  });

  it("failed snapshot routes to onFailed and stops", async () => {
    const fetchMock = respond("failed");
    vi.stubGlobal("fetch", fetchMock);
    const h = handlers();
    const stop = watchProgress("a1", h);
    await vi.advanceTimersByTimeAsync(2_100);
    expect(h.onFailed).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetchMock.mock.calls.length).toBe(1);
    stop();
  });
});
