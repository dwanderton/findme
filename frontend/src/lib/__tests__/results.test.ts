import { describe, expect, it } from "vitest";

import { cameraLine, filterMatches, photoLine, placeLine, shouldRepollVlm, tagCounts, weatherLine, type FindResponse, type Match } from "../results";

const base: Match = {
  photoId: "p1",
  score: 0.63,
  band: "strong",
  bbox: [1, 2, 3, 4],
  thumbUrl: "/photos/p1?thumb=true",
  fullUrl: "/photos/p1",
  takenAt: "2026-09-14T14:20:00",
  camera: { present: true, make: "Sony", model: "ILCE-7M4", focalLengthMm: 35, aperture: 1.8, shutter: "1/250", iso: 400 },
  place: { present: true, source: "google-geocoding", label: "Shoreline Amphitheatre" },
  weather: { present: true, basis: "photo-gps", tempC: 18.4, condition: "clear sky", localTime: "14:20", windKmh: 11.2 },
  vlm: { status: "ready", caption: "You on stage.", tags: ["stage", "indoors"], altText: "Speaker on stage." },
  enrichment: { status: "full" },
};

const m = (over: Partial<Match>): Match => ({ ...base, ...over });

describe("panel lines", () => {
  it("camera full line", () => {
    expect(cameraLine(base.camera)).toBe("Sony ILCE-7M4 · 35mm · f/1.8 · 1/250 · ISO 400");
  });

  it("camera scrubbed", () => {
    expect(cameraLine({ present: false, reason: "exif-stripped" })).toContain("scrubbed");
  });

  it("weather line with venue provenance suffix", () => {
    const line = weatherLine({ ...base.weather, basis: "venue-location" });
    expect(line).toContain("18.4°C · clear sky · 14:20 local");
    expect(line).toContain("user-supplied venue");
  });

  it("absent reasons mapped to honest copy", () => {
    expect(weatherLine({ present: false, reason: "no-gps" })).toBe("no GPS in file");
    expect(weatherLine({ present: false, reason: "no-timestamp" })).toBe("no timestamp in file");
    expect(placeLine({ present: false, reason: "no-gps" })).toBe("no GPS in file");
  });

  it("vlm pending and user-venue place", () => {
    expect(photoLine({ status: "pending" })).toContain("generating");
    expect(placeLine({ present: true, source: "user-venue", label: "Shoreline" })).toContain("user-supplied venue");
  });
});

describe("filters", () => {
  const matches = [
    m({ photoId: "a", band: "strong", vlm: { status: "ready", tags: ["stage"] } }),
    m({ photoId: "b", band: "possible", vlm: { status: "ready", tags: ["stage", "night"] } }),
    m({ photoId: "c", band: "strong", vlm: { status: "ready", tags: [] } }),
  ];

  it("band filter", () => {
    expect(filterMatches(matches, "strong", []).map((x) => x.photoId)).toEqual(["a", "c"]);
  });

  it("tag intersection with band", () => {
    expect(filterMatches(matches, "all", ["stage", "night"]).map((x) => x.photoId)).toEqual(["b"]);
    expect(filterMatches(matches, "strong", ["night"])).toEqual([]);
  });

  it("tag counts sorted", () => {
    expect(tagCounts(matches)).toEqual([
      ["stage", 2],
      ["night", 1],
    ]);
  });
});

describe("vlm repoll", () => {
  const resp = (pending: number, story: string): FindResponse => ({
    album: { id: "a", photos: 10, faces: 20 },
    matches: [],
    story: { status: story },
    enrichmentSummary: {},
    vlmSummary: { ready: 1, pending, unavailable: 0 },
  });

  it("repolls while pending, stops at cap and when done", () => {
    expect(shouldRepollVlm(resp(2, "pending"), 0)).toBe(true);
    expect(shouldRepollVlm(resp(0, "pending"), 3)).toBe(true);
    expect(shouldRepollVlm(resp(0, "ready"), 3)).toBe(false);
    expect(shouldRepollVlm(resp(5, "pending"), 20)).toBe(false);
  });
});
