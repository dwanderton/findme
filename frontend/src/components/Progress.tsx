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

  return (
    <div className="card" data-testid="progress">
      {views.map((v) => (
        <div key={v.key} className="mono" style={{ display: "flex", gap: 10, alignItems: "center", padding: "4px 0", fontSize: "0.8rem", color: v.state === "todo" ? "var(--muted)" : "var(--text)" }}>
          <span className={`dot ${v.state === "active" ? "running" : v.state === "failed" ? "error" : v.state === "done" ? "idle" : "pending"}`} style={v.state === "done" ? { background: "var(--status-running)", animation: "none" } : undefined} />
          <span style={{ minWidth: 190 }}>{v.label}</span>
          {v.state === "active" && (
            <span className="log-stream">
              {snap.photosDone}/{snap.photosTotal} · {pct}%
              {snap.facesFound ? ` · ${snap.facesFound} faces` : ""}
              {eta.confident && eta.etaSec !== null ? ` · ~${eta.etaSec}s left` : ""}
            </span>
          )}
        </div>
      ))}
      {failed && (
        <p className="mono" style={{ color: "var(--status-error)", fontSize: "0.78rem", marginTop: 8 }}>
          indexing failed. retry commit from the upload card.
        </p>
      )}
    </div>
  );
}
