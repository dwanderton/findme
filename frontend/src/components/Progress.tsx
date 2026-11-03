"use client";

import { useEffect, useRef, useState } from "react";

import { COPY } from "@/lib/copy";
import { EtaTracker, stageViews, watchProgress } from "@/lib/progressClient";
import type { ProgressSnapshot } from "@/lib/sse";

const LABELS: Record<string, string> = {
  received: COPY.stageReceived,
  extracting: COPY.stageExtracting,
  embedding: COPY.stageEmbedding,
  ready: COPY.stageReady,
};

export function Progress({ albumId, onReady }: { albumId: string; onReady: (s: ProgressSnapshot) => void }) {
  const [snap, setSnap] = useState<ProgressSnapshot | null>(null);
  const [failed, setFailed] = useState(false);
  const tracker = useRef(new EtaTracker());
  const [eta, setEta] = useState<{ etaSec: number | null; confident: boolean }>({ etaSec: null, confident: false });

  useEffect(() => {
    const stop = watchProgress(albumId, {
      onSnapshot: (s) => {
        tracker.current.observe(Date.now(), s.photosDone);
        setEta(tracker.current.compute(Date.now(), s.photosDone, s.photosTotal));
        setSnap(s);
      },
      onDone: (s) => {
        setSnap(s);
        onReady(s);
      },
      onFailed: (s) => {
        setSnap(s);
        setFailed(true);
      },
    });
    return stop;
  }, [albumId, onReady]);

  if (!snap) return null;
  const views = stageViews(snap.stage, LABELS);
  const pct = snap.photosTotal ? Math.round((snap.photosDone / snap.photosTotal) * 1000) / 10 : 0;

  const current = failed
    ? { key: "failed", label: "indexing failed", state: "failed" as const }
    : (views.find((v) => v.state === "active") ?? views[views.length - 1]);
  const dotClass = current.state === "failed" ? "error" : current.state === "done" ? "idle" : "running";

  return (
    <div className="card" data-testid="progress">
      <div
        key={current.key}
        className="mono log-stream"
        style={{ display: "flex", gap: 10, alignItems: "center", fontSize: "0.82rem" }}
      >
        <span
          className={`dot ${dotClass}`}
          style={current.state === "done" ? { background: "var(--status-running)" } : undefined}
        />
        <span>{current.label}</span>
        {current.state === "active" && (
          <span style={{ color: "var(--muted)" }}>
            {snap.photosDone}/{snap.photosTotal} · {pct}%
            {snap.facesFound ? ` · ${snap.facesFound} faces` : ""}
            {eta.confident && eta.etaSec !== null ? ` · ~${eta.etaSec}s left` : ""}
          </span>
        )}
        {current.state === "failed" && (
          <span style={{ color: "var(--status-error)" }}>create a new album and retry</span>
        )}
      </div>
    </div>
  );
}
