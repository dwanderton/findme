import { describe, expect, it } from "vitest";

import { BATCH_MAX_BYTES, BATCH_MAX_PHOTOS, normalizeExif, planBatches } from "../preprocess";

const item = (size: number) => ({ blob: { size } });

describe("planBatches", () => {
  it("caps by photo count", () => {
    const batches = planBatches(Array.from({ length: 20 }, () => item(1000)));
    expect(batches.length).toBe(3);
    expect(batches[0].length).toBe(BATCH_MAX_PHOTOS);
    expect(batches[2].length).toBe(4);
  });

  it("caps by bytes", () => {
    const big = Math.floor(BATCH_MAX_BYTES / 2) + 1;
    const batches = planBatches([item(big), item(big), item(big)]);
    expect(batches.map((b) => b.length)).toEqual([1, 1, 1]);
  });

  it("single oversize item still ships alone", () => {
    const batches = planBatches([item(BATCH_MAX_BYTES * 2)]);
    expect(batches.length).toBe(1);
  });

  it("empty input", () => {
    expect(planBatches([])).toEqual([]);
  });
});

describe("normalizeExif", () => {
  it("maps exifr fields incl shutter formatting", () => {
    const e = normalizeExif({
      latitude: 37.4,
      longitude: -122.1,
      DateTimeOriginal: new Date("2026-09-14T21:20:11Z"),
      Make: "Sony",
      Model: "ILCE-7M4",
      FNumber: 1.8,
      ExposureTime: 0.004,
      ISO: 400,
      FocalLength: 35,
    });
    expect(e).not.toBeNull();
    expect(e!.gps_present).toBe(true);
    expect(e!.shutter).toBe("1/250");
    expect(e!.taken_at).toBe("2026-09-14T21:20:11");
  });

  it("no useful fields returns null", () => {
    expect(normalizeExif({})).toBeNull();
    expect(normalizeExif(null)).toBeNull();
  });

  it("gps absent flagged", () => {
    const e = normalizeExif({ Make: "Canon" });
    expect(e!.gps_present).toBe(false);
  });
});
