"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { Backdrop } from "@/components/Backdrop";
import { Banners } from "@/components/Banners";
import { DebugConsole } from "@/components/DebugConsole";
import { Enroll } from "@/components/Enroll";
import { Progress } from "@/components/Progress";
import { Results } from "@/components/Results";
import { Upload } from "@/components/Upload";
import { VenueLink } from "@/components/Venue";
import { COPY } from "@/lib/copy";
import { viewTransition } from "@/lib/viewTransition";

const cardLabel: React.CSSProperties = {
  fontSize: "0.62rem",
  letterSpacing: "0.1em",
  color: "var(--primary-text)",
  display: "block",
  marginBottom: 10,
};

function ResultsSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }} data-testid="results-skeleton">
      <div className="skeleton" style={{ width: "40%", height: 16 }} />
      <div style={{ display: "flex", gap: 8 }}>
        <div className="skeleton" style={{ width: 56, height: 26, borderRadius: 999 }} />
        <div className="skeleton" style={{ width: 72, height: 26, borderRadius: 999 }} />
        <div className="skeleton" style={{ width: 64, height: 26, borderRadius: 999 }} />
      </div>
      <div className="skeleton" style={{ width: "100%", height: 320 }} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 10 }}>
        <div className="skeleton" style={{ height: 230 }} />
        <div className="skeleton" style={{ height: 230 }} />
        <div className="skeleton" style={{ height: 230 }} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 10 }}>
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="skeleton" style={{ aspectRatio: "1" }} />
        ))}
      </div>
    </div>
  );
}

const STATUS_RETRY_MS = [2_000, 5_000, 10_000];

export default function AlbumPage({ params }: { params: Promise<{ albumId: string }> }) {
  const { albumId } = use(params);
  const [committed, setCommitted] = useState<boolean | null>(null);
  const [statusFailed, setStatusFailed] = useState(false);
  const [statusNonce, setStatusNonce] = useState(0);

  useEffect(() => {
    const storedUser = localStorage.getItem(`user:${albumId}`);
    if (storedUser) setUserId(storedUser);
    setOwner(localStorage.getItem(`owner:${albumId}`));
    let cancelled = false;
    async function loadStatus(attempt = 0) {
      let s: {
        stage: string;
        gpsCoverage: { withGps: number; total: number };
        venue: { label: string; lat: number; lon: number; source: string } | null;
      } | null = null;
      try {
        const r = await fetch(`/api/albums/${albumId}/status`);
        if (r.status === 404) {
          if (!cancelled) setCommitted(false);
          return;
        }
        if (!r.ok) throw new Error(String(r.status));
        s = await r.json();
      } catch {
        if (cancelled) return;
        const delay = STATUS_RETRY_MS[attempt];
        if (delay !== undefined) setTimeout(() => void loadStatus(attempt + 1), delay);
        else setStatusFailed(true);
        return;
      }
      if (cancelled || !s) return;
      setStatusFailed(false);
      setCommitted(s.stage !== "received");
      if (s.stage === "ready") {
        setReady(true);
        setGps(s.gpsCoverage);
      }
      if (s.venue) setVenue(s.venue);
    }
    void loadStatus();
    return () => {
      cancelled = true;
    };
  }, [albumId, statusNonce]);
  const [tiles, setTiles] = useState<string[]>([]);
  const [servedTiles, setServedTiles] = useState<string[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [owner, setOwner] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [gps, setGps] = useState<{ withGps: number; total: number } | null>(null);
  const [venue, setVenue] = useState<{ label: string; lat: number; lon: number; source: string } | null>(null);
  const needsVenue = Boolean(owner && gps && gps.withGps === 0 && !venue);

  return (
    <>
      <Backdrop uploadUrls={tiles} servedUrls={servedTiles} dimmed={ready} />
      <main style={{ maxWidth: 760, margin: "0 auto", padding: "48px 24px", position: "relative", zIndex: 2 }}>
      <DebugConsole albumId={albumId} />
      <Banners />
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 20 }}>
        <h1 style={{ fontSize: "1.3rem" }}>
          <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
            <span className="logo-dot" aria-hidden /> {COPY.appName}
          </Link>
        </h1>
        <span className="mono" style={{ color: "var(--muted)", fontSize: "0.7rem" }}>
          album {albumId.slice(0, 8)}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {committed === null && !statusFailed && (
          <section className="card card-in" data-testid="album-skeleton">
            <span className="mono" style={cardLabel}>1 · ALBUM</span>
            <div className="skeleton" style={{ width: "55%", height: 14 }} />
            <div className="skeleton" style={{ width: "100%", height: 110, marginTop: 10 }} />
          </section>
        )}
        {statusFailed && (
          <section className="card card-in">
            <p className="mono" style={{ color: "var(--status-error)", fontSize: "0.8rem" }}>{COPY.albumLoadFailed}</p>
            <button
              className="ghost"
              style={{ marginTop: 10 }}
              onClick={() => {
                setStatusFailed(false);
                setStatusNonce((n) => n + 1);
              }}
            >
              retry
            </button>
          </section>
        )}
        {committed === false && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>1 · ALBUM</span>
            <Upload albumId={albumId} onCommitted={() => viewTransition(() => setCommitted(true))} onTiles={setTiles} />
          </section>
        )}
        {committed === true && !ready && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>INDEXING</span>
            <Progress
              albumId={albumId}
              onReady={(s) => viewTransition(() => { setReady(true); setGps(s.gpsCoverage ?? null); })}
            />
          </section>
        )}
        {userId && !ready && <ResultsSkeleton />}
        {ready && !userId && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>2 · YOU</span>
            <Enroll onFind={(uid) => { localStorage.setItem(`user:${albumId}`, uid); viewTransition(() => setUserId(uid)); }} />
          </section>
        )}
        {userId && ready && needsVenue && <VenueLink albumId={albumId} venue={venue} onChange={setVenue} />}
        {userId && ready && !needsVenue && (
          <Results key={venue?.label ?? "none"} albumId={albumId} userId={userId} venue={venue} onVenueChange={setVenue} onThumbs={setServedTiles} />
        )}
      </div>
      </main>
    </>
  );
}
