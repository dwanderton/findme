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
    <main style={{ maxWidth: 760, margin: "0 auto", padding: "48px 24px", position: "relative", zIndex: 1 }}>
      <Backdrop uploadUrls={tiles} servedUrls={servedTiles} dimmed={ready} />
      <DebugConsole albumId={albumId} />
      <Banners />
      <h1 style={{ fontSize: "1.3rem" }}>
        <span style={{ color: "var(--primary)" }}>▲</span> {COPY.appName}
        <span className="mono" style={{ color: "var(--muted)", fontSize: "0.7rem", marginLeft: 12 }}>
          album {albumId.slice(0, 8)}
        </span>
      </h1>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 24 }}>
        {!committed && <Upload albumId={albumId} onCommitted={() => setCommitted(true)} onTiles={setTiles} />}
        {committed && <Progress albumId={albumId} onReady={(s) => { setReady(true); setGps(s.gpsCoverage); }} />}
        <Enroll onFind={(uid) => { localStorage.setItem(`user:${albumId}`, uid); setUserId(uid); }} />
        {userId && !ready && (
          <p className="mono" style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
            enrolled {userId.slice(0, 8)} · waiting for index
          </p>
        )}
        {ready && (venue || (gps && gps.withGps / Math.max(gps.total, 1) < 0.2)) && (
          <VenueLink albumId={albumId} venue={venue} onChange={setVenue} />
        )}
        {userId && ready && <Results key={venue?.label ?? "none"} albumId={albumId} userId={userId} onThumbs={setServedTiles} />}
        <AlbumActions albumId={albumId} userId={userId} ready={ready} />
      </div>
    </main>
  );
}
