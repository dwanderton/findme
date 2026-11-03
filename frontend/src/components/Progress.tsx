"use client";

import { useEffect, useRef, useState } from "react";

import { COPY } from "@/lib/copy";
import { ProgressPacer, type PacedView } from "@/lib/pacing";
import { EtaTracker, watchProgress } from "@/lib/progressClient";
import type { ProgressSnapshot } from "@/lib/sse";

const LABELS: Record<string, string> = {
  received: COPY.stageReceived,
  extracting: COPY.stageExtracting,
  embedding: COPY.stageEmbedding,
  ready: COPY.stageReady,
  failed: "indexing failed",
};

export function Progress({ albumId, onReady }: { albumId: string; onReady: (s: ProgressSnapshot) => void }) {
  const [snap, setSnap] = useState<ProgressSnapshot | null>(null);
  const [view, setView] = useState<PacedView | null>(null);
  const pacer = useRef<ProgressPacer | null>(null);
  const latest = useRef<ProgressSnapshot | null>(null);
  const readyFired = useRef(false);
  const tracker = useRef(new EtaTracker());
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;
  const [eta, setEta] = useState<{ etaSec: number | null; confident: boolean }>({ etaSec: null, confident: false });

  useEffect(() => {
    pacer.current = new ProgressPacer(Date.now());
    const apply = (s: ProgressSnapshot) => {
      latest.current = s;
      pacer.current?.feed(s.stage, s.photosDone, s.photosTotal);
      if (s.stage === "embedding") {
        tracker.current.observe(Date.now(), s.photosDone);
        setEta(tracker.current.compute(Date.now(), s.photosDone, s.photosTotal));
      }
      setSnap(s);
    };
    const stop = watchProgress(albumId, { onSnapshot: apply, onDone: apply, onFailed: apply });
    const interval = setInterval(() => {
      if (!pacer.current) return;
      const v = pacer.current.tick(Date.now());
      setView(v);
      if (v.stage === "ready" && !readyFired.current && latest.current) {
        readyFired.current = true;
        onReadyRef.current(latest.current);
      }
    }, 50);
    return () => {
      stop();
      clearInterval(interval);
    };
  }, [albumId]);

  if (!snap || !view) return null;
  const total = snap.photosTotal;
  const pct = total ? Math.round((view.done / total) * 1000) / 10 : 0;
  const active = view.stage !== "ready" && view.stage !== "failed";
  const dotClass = view.stage === "failed" ? "error" : view.stage === "ready" ? "idle" : "running";

  return (
    <div data-testid="progress">
      <div
        key={view.stage}
        className="mono log-stream"
        style={{ display: "flex", gap: 10, alignItems: "center", fontSize: "0.82rem" }}
      >
        <span
          className={`dot ${dotClass}`}
          style={view.stage === "ready" ? { background: "var(--status-running)" } : undefined}
        />
        <span>{LABELS[view.stage] ?? view.stage}</span>
        {active && total > 0 && (
          <span style={{ color: "var(--muted)" }}>
            {view.done}/{total} · {pct}%
            {view.stage === "embedding" && snap.facesFound ? ` · ${snap.facesFound} faces` : ""}
            {view.stage === "embedding" && eta.confident && eta.etaSec !== null ? ` · ~${eta.etaSec}s left` : ""}
          </span>
        )}
        {view.stage === "failed" && (
          <span style={{ color: "var(--status-error)" }}>create a new album and retry</span>
        )}
      </div>
    </div>
  );
}
