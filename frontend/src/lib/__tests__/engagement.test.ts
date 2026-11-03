import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IDLE_MS, watchEngagement } from "../engagement";

describe("watchEngagement", () => {
  let hidden = false;

  const setHidden = (value: boolean) => {
    hidden = value;
    document.dispatchEvent(new Event("visibilitychange"));
  };

  beforeEach(() => {
    vi.useFakeTimers();
    hidden = false;
    Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("goes idle after five minutes without interaction", () => {
    const onChange = vi.fn();
    const stop = watchEngagement(onChange);
    vi.advanceTimersByTime(IDLE_MS - 1000);
    expect(onChange).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(onChange).toHaveBeenCalledWith(false);
    stop();
  });

  it("interaction resets the idle clock and re-engages after idle", () => {
    const onChange = vi.fn();
    const stop = watchEngagement(onChange);
    vi.advanceTimersByTime(IDLE_MS - 1000);
    window.dispatchEvent(new Event("keydown"));
    vi.advanceTimersByTime(IDLE_MS - 1000);
    expect(onChange).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(onChange).toHaveBeenCalledWith(false);
    window.dispatchEvent(new Event("pointermove"));
    expect(onChange).toHaveBeenLastCalledWith(true);
    stop();
  });

  it("hidden tab disengages immediately, visible re-engages with a fresh clock", () => {
    const onChange = vi.fn();
    const stop = watchEngagement(onChange);
    setHidden(true);
    expect(onChange).toHaveBeenLastCalledWith(false);
    setHidden(false);
    expect(onChange).toHaveBeenLastCalledWith(true);
    vi.advanceTimersByTime(IDLE_MS);
    expect(onChange).toHaveBeenLastCalledWith(false);
    stop();
  });

  it("interaction while hidden does not re-engage", () => {
    const onChange = vi.fn();
    const stop = watchEngagement(onChange);
    setHidden(true);
    expect(onChange).toHaveBeenLastCalledWith(false);
    window.dispatchEvent(new Event("pointermove"));
    expect(onChange).toHaveBeenLastCalledWith(false);
    expect(onChange.mock.calls.filter(([v]) => v === true)).toHaveLength(0);
    stop();
  });

  it("cleanup stops all reporting", () => {
    const onChange = vi.fn();
    const stop = watchEngagement(onChange);
    stop();
    vi.advanceTimersByTime(IDLE_MS * 2);
    setHidden(true);
    window.dispatchEvent(new Event("keydown"));
    expect(onChange).not.toHaveBeenCalled();
  });
});
