"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { Backdrop } from "@/components/Backdrop";
import { Banners } from "@/components/Banners";
import { DebugConsole } from "@/components/DebugConsole";
import { Enroll } from "@/components/Enroll";
import { Progress } from "@/components/Progress";
import { AlbumActions, Results } from "@/components/Results";
import { Upload } from "@/components/Upload";
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

export default function AlbumPage({ params }: { params: Promise<{ albumId: string }> }) {
  const { albumId } = use(params);
  const [committed, setCommitted] = useState<boolean | null>(null);

  useEffect(() => {
    const storedUser = localStorage.getItem(`user:${albumId}`);
    if (storedUser) setUserId(storedUser);
    void fetch(`/api/albums/${albumId}/status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => {
        if (!s) {
          setCommitted(false);
          return;
        }
        setCommitted(s.stage !== "received");
        if (s.stage === "ready") setReady(true);
      })
      .catch(() => setCommitted(false));
  }, [albumId]);
  const [tiles, setTiles] = useState<string[]>([]);
  const [servedTiles, setServedTiles] = useState<string[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [venue, setVenue] = useState<{ label: string; lat: number; lon: number; source: string } | null>(null);

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
        {committed === false && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>1 · ALBUM</span>
            <Upload albumId={albumId} onCommitted={() => viewTransition(() => setCommitted(true))} onTiles={setTiles} />
          </section>
        )}
        {committed === true && !ready && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>INDEXING</span>
            <Progress albumId={albumId} onReady={() => viewTransition(() => setReady(true))} />
          </section>
        )}
        {committed !== null && !ready && !userId && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>2 · YOU</span>
            <Enroll onFind={(uid) => { localStorage.setItem(`user:${albumId}`, uid); viewTransition(() => setUserId(uid)); }} />
          </section>
        )}
        {userId && !ready && <ResultsSkeleton />}
        {ready && !userId && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>2 · YOU</span>
            <Enroll onFind={(uid) => { localStorage.setItem(`user:${albumId}`, uid); viewTransition(() => setUserId(uid)); }} />
          </section>
        )}
        {userId && ready && (
          <Results key={venue?.label ?? "none"} albumId={albumId} userId={userId} venue={venue} onVenueChange={setVenue} onThumbs={setServedTiles} />
        )}
        <AlbumActions albumId={albumId} userId={userId} ready={ready} />
      </div>
      </main>
    </>
  );
}
