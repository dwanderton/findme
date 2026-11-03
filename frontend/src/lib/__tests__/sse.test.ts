import { describe, expect, it } from "vitest";

import { diffToEvents, encodeEvent, terminal, type ProgressSnapshot } from "../sse";

const snap = (stage: string, done: number, faces = 0): ProgressSnapshot => ({
  stage,
  photosTotal: 100,
  photosDone: done,
  facesFound: faces,
});

describe("sse relay logic", () => {
  it("first snapshot emits progress", () => {
    const events = diffToEvents(null, snap("extracting", 10), 1);
    expect(events.map((e) => e.event)).toEqual(["progress"]);
    expect(events[0].id).toBe(1);
  });

  it("stage transition emits stage then progress, ids monotonic", () => {
    const events = diffToEvents(snap("extracting", 90), snap("embedding", 0), 5);
    expect(events.map((e) => e.event)).toEqual(["stage", "progress"]);
    expect(events.map((e) => e.id)).toEqual([5, 6]);
  });

  it("no change emits nothing", () => {
    expect(diffToEvents(snap("embedding", 50, 7), snap("embedding", 50, 7), 3)).toEqual([]);
  });

  it("ready emits done and is terminal", () => {
    const events = diffToEvents(snap("embedding", 99), snap("ready", 100), 9);
    expect(events.map((e) => e.event)).toEqual(["stage", "done"]);
    expect(terminal(snap("ready", 100))).toBe(true);
    expect(terminal(snap("embedding", 1))).toBe(false);
  });

  it("failed emits failed", () => {
    const events = diffToEvents(snap("embedding", 10), snap("failed", 10), 1);
    expect(events.map((e) => e.event)).toContain("failed");
  });

  it("wire format carries id/event/data", () => {
    const wire = encodeEvent({ id: 4, event: "progress", data: snap("embedding", 42, 99) });
    expect(wire).toContain("id: 4\n");
    expect(wire).toContain("event: progress\n");
    expect(wire).toContain('"photosDone":42');
    expect(wire.endsWith("\n\n")).toBe(true);
  });
});
