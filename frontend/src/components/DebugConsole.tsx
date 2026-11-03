"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  clientEvents,
  filterEvents,
  installFetchInterceptor,
  shouldToggleOnBacktick,
  type AnyEvent,
  type Filter,
} from "@/lib/debugLog";

const FILTERS: Filter[] = ["all", "client", "server", "external", "errors"];

export function DebugConsole({ albumId }: { albumId?: string }) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [highlight, setHighlight] = useState<string | undefined>(undefined);
  const [serverEvents, setServerEvents] = useState<AnyEvent[]>([]);
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    installFetchInterceptor();
    setOpen(localStorage.getItem("debug:open") === "1");
    const persist = (next: boolean) => {
      localStorage.setItem("debug:open", next ? "1" : "0");
      return next;
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "`" && shouldToggleOnBacktick(e.target)) {
        e.preventDefault();
        setOpen((o) => persist(!o));
      }
      if (e.key === "Escape") setOpen(() => persist(false));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const cursor = useRef(0);

  const refresh = useCallback(async () => {
    if (!albumId) return;
    try {
      // Pages are 200 events; loop until the server has no more for this cursor.
      for (let page = 0; page < 10; page++) {
        const r = await fetch(`/api/debug/${albumId}?cursor=${cursor.current}`);
        if (!r.ok) return;
        const body = await r.json();
        // Backend ts is epoch seconds; client events use Date.now() ms. Normalize to ms so the merge interleaves.
        const events = (body.events as AnyEvent[]).map((e) => ({
          ...e,
          ts: typeof e.ts === "number" ? e.ts * 1000 : e.ts,
        }));
        cursor.current = body.cursor;
        setSnapshot(body.snapshot);
        if (events.length > 0) setServerEvents((prev) => [...prev, ...events].slice(-1000));
        if (events.length < 200) break;
      }
    } catch {}
  }, [albumId]);

  useEffect(() => {
    cursor.current = 0;
    setServerEvents([]);
  }, [albumId]);

  useEffect(() => {
    if (!open) return;
    void refresh();
    const t = setInterval(refresh, 2000);
    document.body.style.paddingBottom = "44vh";
    return () => {
      clearInterval(t);
      document.body.style.paddingBottom = "";
    };
  }, [open, refresh]);

  if (!open) return null;

  const merged = [...serverEvents, ...clientEvents()].sort((a, b) => (a.ts ?? 0) - (b.ts ?? 0));
  const visible = filterEvents(merged, filter, highlight).slice(-200);
  const circuits = (snapshot?.circuits as Record<string, string>) ?? {};

  return (
    <div
      data-testid="debug-console"
      className="mono"
      style={{
        position: "fixed",
        left: 0,
        right: 0,
        bottom: 0,
        height: "42vh",
        background: "var(--surface)",
        borderTop: "1px solid var(--primary)",
        zIndex: 50,
        display: "flex",
        flexDirection: "column",
        fontSize: "0.72rem",
      }}
    >
      <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "8px 14px", borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
        <span style={{ color: "var(--primary-text)" }}>trace</span>
        {FILTERS.map((f) => (
          <button key={f} className={`chip ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)}>
            {f}
          </button>
        ))}
        {highlight && (
          <button className="chip active" onClick={() => setHighlight(undefined)}>
            req {highlight.slice(0, 8)} ×
          </button>
        )}
        <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
          {Object.entries(circuits).length > 0 && (
            <span style={{ color: "var(--muted)" }}>
              {Object.entries(circuits)
                .map(([name, state]) => `${name}: ${state}`)
                .join(" · ")}
            </span>
          )}
          <button
            className="chip"
            onClick={() => void navigator.clipboard.writeText(JSON.stringify({ events: merged, snapshot }, null, 2))}
          >
            copy trace
          </button>
        </div>
      </div>
      <div style={{ overflowY: "auto", padding: "6px 14px", flex: 1 }}>
        {visible.map((e, i) => (
          <div
            key={`${e.src}-${e.seq}-${i}`}
            className="log-stream"
            style={{
              display: "flex",
              gap: 10,
              padding: "1px 0",
              color: e.level === "error" ? "var(--status-error)" : e.level === "warn" ? "var(--status-pending)" : "var(--muted)",
              cursor: e.requestId ? "pointer" : "default",
            }}
            onClick={() => e.requestId && setHighlight(e.requestId)}
          >
            <span style={{ minWidth: 56, color: "var(--primary-text)" }}>{e.src}</span>
            <span style={{ minWidth: 130 }}>{e.event}</span>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {e.data ? JSON.stringify(e.data) : ""}
            </span>
          </div>
        ))}
        {visible.length === 0 && <span style={{ color: "var(--muted)" }}>no events yet</span>}
      </div>
    </div>
  );
}
