"use client";

import { use, useEffect, useState } from "react";

import { Backdrop } from "@/components/Backdrop";
import { Banners } from "@/components/Banners";
import { DebugConsole } from "@/components/DebugConsole";
import { Enroll } from "@/components/Enroll";
import { Progress } from "@/components/Progress";
import { AlbumActions, Results } from "@/components/Results";
import { VenueLink } from "@/components/Venue";
import { Upload } from "@/components/Upload";
import { COPY } from "@/lib/copy";

const cardLabel: React.CSSProperties = {
  fontSize: "0.62rem",
  letterSpacing: "0.1em",
  color: "var(--primary-text)",
  display: "block",
  marginBottom: 10,
};

export default function AlbumPage({ params }: { params: Promise<{ albumId: string }> }) {
  const { albumId } = use(params);
  const [committed, setCommitted] = useState(false);

  useEffect(() => {
    const storedUser = localStorage.getItem(`user:${albumId}`);
    if (storedUser) setUserId(storedUser);
    void fetch(`/api/albums/${albumId}/status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => {
        if (!s) return;
        if (s.stage !== "received") setCommitted(true);
        if (s.stage === "ready") {
          setReady(true);
          setGps(s.gpsCoverage);
        }
      })
      .catch(() => {});
  }, [albumId]);
  const [tiles, setTiles] = useState<string[]>([]);
  const [servedTiles, setServedTiles] = useState<string[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [venue, setVenue] = useState<{ label: string; lat: number; lon: number; source: string } | null>(null);
  const [gps, setGps] = useState<{ withGps: number; total: number } | undefined>(undefined);

  return (
    <>
      <Backdrop uploadUrls={tiles} servedUrls={servedTiles} dimmed={ready} />
      <main style={{ maxWidth: 760, margin: "0 auto", padding: "48px 24px", position: "relative", zIndex: 2 }}>
      <DebugConsole albumId={albumId} />
      <Banners />
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 20 }}>
        <h1 style={{ fontSize: "1.3rem" }}>
          <span style={{ color: "var(--primary)" }}>▲</span> {COPY.appName}
        </h1>
        <span className="mono" style={{ color: "var(--muted)", fontSize: "0.7rem" }}>
          album {albumId.slice(0, 8)}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {!committed && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>1 · ALBUM</span>
            <Upload albumId={albumId} onCommitted={() => setCommitted(true)} onTiles={setTiles} />
          </section>
        )}
        {committed && !ready && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>INDEXING</span>
            <Progress albumId={albumId} onReady={(s) => { setReady(true); setGps(s.gpsCoverage); }} />
          </section>
        )}
        {!ready && !userId && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>2 · YOU</span>
            <Enroll onFind={(uid) => { localStorage.setItem(`user:${albumId}`, uid); setUserId(uid); }} />
          </section>
        )}
        {userId && !ready && (
          <p className="mono" style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
            enrolled {userId.slice(0, 8)} · waiting for index
          </p>
        )}
        {ready && !userId && (
          <section className="card card-in">
            <span className="mono" style={cardLabel}>2 · YOU</span>
            <Enroll onFind={(uid) => { localStorage.setItem(`user:${albumId}`, uid); setUserId(uid); }} />
          </section>
        )}
        {ready && (venue || (gps && gps.withGps / Math.max(gps.total, 1) < 0.2)) && (
          <VenueLink albumId={albumId} venue={venue} onChange={setVenue} />
        )}
        {userId && ready && <Results key={venue?.label ?? "none"} albumId={albumId} userId={userId} onThumbs={setServedTiles} />}
        <AlbumActions albumId={albumId} userId={userId} ready={ready} />
      </div>
      </main>
    </>
  );
}
