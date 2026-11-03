import { describe, expect, it, vi } from "vitest";

import { debounce, lowGps } from "../debounce";

describe("debounce", () => {
  it("fires once after quiet period with last args", async () => {
    vi.useFakeTimers();
    const calls: string[] = [];
    const d = debounce((q: string) => calls.push(q), 300);
    d("a");
    d("ab");
    d("abc");
    vi.advanceTimersByTime(299);
    expect(calls).toEqual([]);
    vi.advanceTimersByTime(2);
    expect(calls).toEqual(["abc"]);
    vi.useRealTimers();
  });

  it("cancel prevents firing", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const d = debounce(fn, 100);
    d();
    d.cancel();
    vi.advanceTimersByTime(200);
    expect(fn).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
});

describe("lowGps banner trigger", () => {
  it("under 20 percent triggers", () => {
    expect(lowGps({ withGps: 1, total: 10 })).toBe(true);
    expect(lowGps({ withGps: 0, total: 50 })).toBe(true);
  });

  it("at or above 20 percent does not", () => {
    expect(lowGps({ withGps: 2, total: 10 })).toBe(false);
    expect(lowGps({ withGps: 9, total: 10 })).toBe(false);
  });

  it("empty or missing coverage stays quiet", () => {
    expect(lowGps(undefined)).toBe(false);
    expect(lowGps({ withGps: 0, total: 0 })).toBe(false);
  });
});
