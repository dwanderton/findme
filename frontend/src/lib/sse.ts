export type ProgressSnapshot = {
  stage: string;
  photosTotal: number;
  photosDone: number;
  facesFound: number;
  gpsCoverage?: { withGps: number; total: number };
  error?: unknown;
};

export type SseEvent = { id: number; event: string; data: ProgressSnapshot };

export function diffToEvents(prev: ProgressSnapshot | null, cur: ProgressSnapshot, seq: number): SseEvent[] {
  const out: SseEvent[] = [];
  if (prev && prev.stage !== cur.stage) {
    out.push({ id: seq + out.length, event: "stage", data: cur });
  }
  if (cur.stage === "ready") {
    out.push({ id: seq + out.length, event: "done", data: cur });
  } else if (cur.stage === "failed") {
    out.push({ id: seq + out.length, event: "failed", data: cur });
  } else if (!prev || prev.photosDone !== cur.photosDone || prev.stage !== cur.stage || prev.facesFound !== cur.facesFound) {
    out.push({ id: seq + out.length, event: "progress", data: cur });
  }
  return out;
}

export function encodeEvent(e: SseEvent): string {
  return `id: ${e.id}\nevent: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`;
}

export function terminal(cur: ProgressSnapshot): boolean {
  return cur.stage === "ready" || cur.stage === "failed";
}
