import { beforeEach, describe, expect, it } from "vitest";

import {
  RING_CAP,
  clientEvents,
  filterEvents,
  pushClientEvent,
  resetClientEvents,
  shouldToggleOnBacktick,
  type AnyEvent,
} from "../debugLog";

describe("client ring buffer", () => {
  beforeEach(resetClientEvents);

  it("caps at ring size keeping newest", () => {
    for (let i = 0; i < RING_CAP + 20; i++) pushClientEvent(`e${i}`, "info", {});
    const events = clientEvents();
    expect(events.length).toBe(RING_CAP);
    expect(events[events.length - 1].event).toBe(`e${RING_CAP + 19}`);
  });
});

describe("filters + correlation", () => {
  const events: AnyEvent[] = [
    { seq: 1, src: "client", level: "info", event: "fetch", requestId: "r1" },
    { seq: 2, src: "find", level: "info", event: "search.done", requestId: "r1" },
    { seq: 3, src: "external", level: "warn", event: "geocode.retry", requestId: "r2" },
    { seq: 4, src: "gpu-qb", level: "error", event: "photo.failed" },
  ];

  it("source filters", () => {
    expect(filterEvents(events, "client").map((e) => e.seq)).toEqual([1]);
    expect(filterEvents(events, "server").map((e) => e.seq)).toEqual([2, 4]);
    expect(filterEvents(events, "external").map((e) => e.seq)).toEqual([3]);
  });

  it("errors filter catches warn and error", () => {
    expect(filterEvents(events, "errors").map((e) => e.seq)).toEqual([3, 4]);
  });

  it("requestId correlation across sources", () => {
    expect(filterEvents(events, "all", "r1").map((e) => e.seq)).toEqual([1, 2]);
  });
});

describe("backtick guard", () => {
  it("allows toggle on plain targets, blocks on inputs", () => {
    expect(shouldToggleOnBacktick(null)).toBe(true);
    const input = document.createElement("input");
    expect(shouldToggleOnBacktick(input)).toBe(false);
    const area = document.createElement("textarea");
    expect(shouldToggleOnBacktick(area)).toBe(false);
    const div = document.createElement("div");
    expect(shouldToggleOnBacktick(div)).toBe(true);
  });
});
