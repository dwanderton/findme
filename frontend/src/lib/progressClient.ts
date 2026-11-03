import type { ProgressSnapshot } from "./sse";

export const STAGES = ["received", "extracting", "embedding", "ready"] as const;

export type EtaView = { rate: number; etaSec: number | null; confident: boolean };

const WINDOW_MS = 30_000;
const MIN_PCT = 10;
const MIN_SAMPLE_MS = 10_000;

export class EtaTracker {
  private samples: { t: number; done: number }[] = [];

  observe(t: number, done: number) {
    this.samples.push({ t, done });
    const cutoff = t - WINDOW_MS * 2;
    this.samples = this.samples.filter((s) => s.t >= cutoff);
  }

  compute(now: number, done: number, total: number): EtaView {
    const window = this.samples.filter((s) => s.t >= now - WINDOW_MS);
    let rate = 0;
    if (window.length >= 2) {
      const dt = (window[window.length - 1].t - window[0].t) / 1000;
      const dd = window[window.length - 1].done - window[0].done;
      if (dt > 0) rate = dd / dt;
    }
    const span = this.samples.length >= 2 ? this.samples[this.samples.length - 1].t - this.samples[0].t : 0;
    const pct = total ? (done / total) * 100 : 0;
    const confident = rate > 0 && pct >= MIN_PCT && span >= MIN_SAMPLE_MS;
    const etaSec = confident ? Math.round((total - done) / rate / 5) * 5 : null;
    return { rate: Math.round(rate * 10) / 10, etaSec, confident };
  }
}

export type StageView = { key: string; label: string; state: "done" | "active" | "todo" | "failed" };

export function stageViews(current: string, labels: Record<string, string>): StageView[] {
  if (current === "failed") {
    return STAGES.map((s) => ({ key: s, label: labels[s] ?? s, state: "failed" as const }));
  }
  const idx = STAGES.indexOf(current as (typeof STAGES)[number]);
  return STAGES.map((s, i) => ({
    key: s,
    label: labels[s] ?? s,
    state: i < idx ? "done" : i === idx ? (current === "ready" ? "done" : "active") : "todo",
  }));
}

export function shouldDowngrade(sseFailures: number): boolean {
  return sseFailures >= 2;
}

export type ProgressHandlers = {
  onSnapshot: (s: ProgressSnapshot) => void;
  onDone: (s: ProgressSnapshot) => void;
  onFailed: (s: ProgressSnapshot) => void;
};

/* The stream exists only while results are awaited and the tab is visible.
 * A terminal snapshot (ready/failed) closes every transport for good, and a
 * hidden tab closes them until the tab is visible again — an open stream
 * makes the proxy poll the backend continuously, which keeps a GPU worker
 * billing. */
export function watchProgress(albumId: string, handlers: ProgressHandlers): () => void {
  let stopped = false;
  let terminal = false;
  let failures = 0;
  let es: EventSource | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  const closeTransports = () => {
    es?.close();
    es = null;
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const route = (s: ProgressSnapshot) => {
    if (s.stage === "ready" || s.stage === "failed") {
      terminal = true;
      closeTransports();
    }
    if (s.stage === "ready") handlers.onDone(s);
    else if (s.stage === "failed") handlers.onFailed(s);
    else handlers.onSnapshot(s);
  };

  const startPolling = () => {
    if (pollTimer || stopped || terminal) return;
    pollTimer = setInterval(async () => {
      try {
        const r = await fetch(`/api/albums/${albumId}/status`, { cache: "no-store" });
        if (r.ok) route((await r.json()) as ProgressSnapshot);
      } catch {}
    }, 2000);
  };

  const startSse = () => {
    if (es || stopped || terminal) return;
    es = new EventSource(`/api/albums/${albumId}/events`);
    const parse = (e: MessageEvent) => route(JSON.parse(e.data) as ProgressSnapshot);
    es.addEventListener("progress", parse);
    es.addEventListener("stage", parse);
    es.addEventListener("done", parse);
    es.addEventListener("failed", parse);
    es.onerror = () => {
      failures += 1;
      if (shouldDowngrade(failures)) {
        closeTransports();
        startPolling();
      }
    };
  };

  const start = () => {
    if (stopped || terminal) return;
    if (typeof document !== "undefined" && document.hidden) return;
    if (typeof EventSource !== "undefined" && !shouldDowngrade(failures)) startSse();
    else startPolling();
  };

  const onVisibility = () => {
    if (document.hidden) closeTransports();
    else start();
  };
  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onVisibility);
  }

  start();

  return () => {
    stopped = true;
    if (typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", onVisibility);
    }
    closeTransports();
  };
}
