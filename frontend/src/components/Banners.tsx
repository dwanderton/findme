"use client";

import { useEffect, useState } from "react";

import { COPY } from "@/lib/copy";
import { classify, countdown, type UiError } from "@/lib/errorState";

export function reportApiError(status: number, code: string | undefined, retryAfter: string | null) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("findme:apierror", { detail: classify(status, code, retryAfter) }));
}

export function Banners() {
  const [error, setError] = useState<UiError | null>(null);
  const [startedAt, setStartedAt] = useState(0);
  const [tick, setTick] = useState(0);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const onError = (e: Event) => {
      const detail = (e as CustomEvent<UiError>).detail;
      if (detail.kind === "validation") return;
      setError(detail);
      setStartedAt(Date.now());
    };
    const onOnline = () => setOffline(false);
    const onOffline = () => setOffline(true);
    window.addEventListener("findme:apierror", onError);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("findme:apierror", onError);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    if (!error?.retryAfterS) return;
    const t = setInterval(() => setTick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [error]);

  const remaining = error?.retryAfterS ? countdown(error.retryAfterS, (Date.now() - startedAt) / 1000) : 0;

  useEffect(() => {
    if (error?.retryAfterS && remaining === 0) setError(null);
  }, [remaining, error]);

  if (offline) {
    return (
      <div className="mono" role="status" style={bannerStyle("var(--status-pending)")}>
        {COPY.offline}
      </div>
    );
  }
  if (!error) return null;

  if (error.kind === "rate-limited") {
    return (
      <div className="mono" role="status" style={bannerStyle("var(--status-pending)")}>
        {COPY.rateLimited} {remaining}s
      </div>
    );
  }
  if (error.kind === "cold-start") {
    return (
      <div className="mono" role="status" style={bannerStyle("var(--primary-text)")}>
        <span className="dot running" style={{ marginRight: 8 }} />
        {COPY.coldStart} · {remaining}s
      </div>
    );
  }
  if (error.kind === "upstream") {
    return (
      <div className="mono" role="alert" style={bannerStyle("var(--status-error)")}>
        {error.message}
      </div>
    );
  }
  return null;
}

function bannerStyle(color: string): React.CSSProperties {
  return {
    position: "fixed",
    top: 12,
    left: "50%",
    transform: "translateX(-50%)",
    background: "var(--surface-2)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "8px 16px",
    fontSize: "0.78rem",
    color,
    zIndex: 60,
  };
}
