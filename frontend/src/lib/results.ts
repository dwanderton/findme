import { COPY } from "./copy";

export type Match = {
  photoId: string;
  score: number;
  band: "strong" | "possible";
  bbox: number[];
  thumbUrl: string;
  fullUrl: string;
  takenAt?: string;
  fileModified?: string;
  camera: { present: boolean; reason?: string; make?: string; model?: string; lens?: string; focalLengthMm?: number; aperture?: number; shutter?: string; iso?: number };
  place: { present: boolean; reason?: string; source?: string; label?: string; lat?: number; lon?: number };
  weather: { present: boolean; reason?: string; basis?: string; tempC?: number; condition?: string; windKmh?: number; localTime?: string };
  vlm: { status: string; caption?: string; tags?: string[]; altText?: string };
  enrichment: { status: string };
};

export type FindResponse = {
  album: { id: string; photos: number; faces: number };
  matches: Match[];
  enrichmentSummary: Record<string, number>;
  vlmSummary: { ready: number; pending: number; unavailable: number };
  gpsCoverage?: { withGps: number; total: number };
};

export function cameraParts(c: Match["camera"]): string[] {
  if (!c.present) return [];
  return [
    [c.make, c.model].filter(Boolean).join(" "),
    c.focalLengthMm ? `${c.focalLengthMm}mm` : null,
    c.aperture ? `f/${c.aperture}` : null,
    c.shutter ?? null,
    c.iso ? `ISO ${c.iso}` : null,
  ].filter((p): p is string => Boolean(p));
}

export function cameraLine(c: Match["camera"]): string {
  return cameraParts(c).join(" · ");
}

export function weatherLine(w: Match["weather"]): string {
  if (!w.present) {
    if (w.reason === "no-gps") return COPY.noGps;
    if (w.reason === "no-timestamp") return "no timestamp in file";
    if (w.reason === "deferred") return "deferred. refresh to enrich";
    return COPY.weatherFailed;
  }
  const parts = [
    w.tempC !== undefined ? `${w.tempC}°C` : null,
    w.condition ?? null,
    w.localTime ? `${w.localTime} local` : null,
    w.windKmh ? `wind ${w.windKmh} km/h` : null,
  ].filter(Boolean);
  return parts.join(" · ");
}

export function placeLine(p: Match["place"]): string {
  if (!p.present) {
    if (p.reason === "no-gps") return COPY.noGps;
    if (p.reason === "deferred") return "deferred. refresh to enrich";
    return "place lookup failed. retry";
  }
  return p.label ?? "";
}

export function photoLine(v: Match["vlm"]): string {
  if (v.status === "ready" && v.caption) return v.caption;
  if (v.status === "pending") return COPY.captionPending;
  return "captions unavailable";
}

export function altText(m: Match): string {
  if (m.vlm.status === "ready" && m.vlm.altText) return m.vlm.altText;
  return `match ${m.band} ${m.score.toFixed(2)}${m.takenAt ? `, taken ${m.takenAt.slice(0, 10)}` : ""}`;
}

export function tagCounts(matches: Match[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const m of matches) {
    for (const t of m.vlm.tags ?? []) counts.set(t, (counts.get(t) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

export function filterMatches(matches: Match[], band: "strong" | "all", tags: string[]): Match[] {
  return matches.filter((m) => {
    if (band === "strong" && m.band !== "strong") return false;
    if (tags.length && !tags.every((t) => m.vlm.tags?.includes(t))) return false;
    return true;
  });
}

export function shouldRepollVlm(resp: FindResponse, attempts: number, maxAttempts = 20): boolean {
  return attempts < maxAttempts && resp.vlmSummary.pending > 0;
}
