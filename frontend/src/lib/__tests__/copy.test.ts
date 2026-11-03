import { describe, expect, it } from "vitest";

import { BANNED_PATTERNS, COPY } from "../copy";

describe("voice rule 8: no llm tell-tales in product copy", () => {
  const entries = Object.entries(COPY);

  it("every copy string passes the banned list", () => {
    const violations: string[] = [];
    for (const [key, value] of entries) {
      for (const pattern of BANNED_PATTERNS) {
        if (pattern.test(value)) violations.push(`${key}: ${pattern}`);
      }
    }
    expect(violations).toEqual([]);
  });

  it("spelling: Runpod never RunPod", () => {
    for (const [, value] of entries) {
      expect(value.includes("RunPod")).toBe(false);
    }
  });
});
