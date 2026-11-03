import { describe, expect, it } from "vitest";

import { canAddMore, canFind, enrollReducer, initialEnroll } from "../enrollState";

const face = (i: number) => ({ selfie: i, facePx: 120 + i, multipleFaces: false });

describe("enroll state machine", () => {
  it("single selfie success enables find", () => {
    let s = enrollReducer(initialEnroll, { type: "submit", names: ["me.jpg"] });
    expect(s.busy).toBe(true);
    expect(canFind(s)).toBe(false);
    s = enrollReducer(s, { type: "success", userId: "u1", faces: [face(0)] });
    expect(s.userId).toBe("u1");
    expect(s.chips[0]).toMatchObject({ state: "ok", facePx: 120 });
    expect(canFind(s)).toBe(true);
    expect(canAddMore(s)).toBe(true);
  });

  it("failure marks named selfie and surfaces error", () => {
    let s = enrollReducer(initialEnroll, { type: "submit", names: ["a.jpg", "b.jpg"] });
    s = enrollReducer(s, { type: "failure", message: "No face found.", selfie: 1 });
    expect(s.chips[1].state).toBe("failed");
    expect(s.error).toBe("No face found.");
    expect(canFind(s)).toBe(false);
  });

  it("append keeps ok chips and stops at five", () => {
    let s = enrollReducer(initialEnroll, { type: "submit", names: ["a", "b", "c"] });
    s = enrollReducer(s, { type: "success", userId: "u1", faces: [face(0), face(1), face(2)] });
    s = enrollReducer(s, { type: "submit", names: ["d", "e"] });
    expect(s.chips.length).toBe(5);
    s = enrollReducer(s, { type: "success", userId: "u1", faces: [face(3), face(4)] });
    expect(s.chips.filter((c) => c.state === "ok").length).toBe(5);
    expect(canAddMore(s)).toBe(false);
    expect(canFind(s)).toBe(true);
  });

  it("multipleFaces carried to chip", () => {
    let s = enrollReducer(initialEnroll, { type: "submit", names: ["g.jpg"] });
    s = enrollReducer(s, {
      type: "success",
      userId: "u2",
      faces: [{ selfie: 0, facePx: 90, multipleFaces: true }],
    });
    expect(s.chips[0].multipleFaces).toBe(true);
  });
});
