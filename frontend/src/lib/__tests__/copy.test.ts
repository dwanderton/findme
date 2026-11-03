import { describe, expect, it } from "vitest";

import { BANNED_PATTERNS, COPY, REJECT_REASONS, rejectionLine } from "../copy";

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

  it("rejection reason copy passes the banned list", () => {
    for (const value of Object.values(REJECT_REASONS)) {
      for (const pattern of BANNED_PATTERNS) {
        expect(pattern.test(value)).toBe(false);
      }
    }
  });
});

describe("rejectionLine", () => {
  it("maps known reasons to readable copy", () => {
    expect(rejectionLine({ name: "broken.jpg", reason: "undecodable" })).toBe("broken.jpg: file could not be read");
    expect(rejectionLine({ name: "a.jpg", reason: "duplicate" })).toBe("a.jpg: duplicate of another photo");
    expect(rejectionLine({ name: "doc.pdf", reason: "UNSUPPORTED_MEDIA" })).toBe("doc.pdf: not a supported image format");
  });

  it("falls back to the raw reason", () => {
    expect(rejectionLine({ name: "x.jpg", reason: "mystery" })).toBe("x.jpg: mystery");
  });
});
