"use client";

import { use, useState } from "react";

import { Backdrop } from "@/components/Backdrop";
import { Enroll } from "@/components/Enroll";
import { Progress } from "@/components/Progress";
import { AlbumActions, Results } from "@/components/Results";
import { Upload } from "@/components/Upload";
import { COPY } from "@/lib/copy";

export default function AlbumPage({ params }: { params: Promise<{ albumId: string }> }) {
  const { albumId } = use(params);
  const [committed, setCommitted] = useState(false);
  const [tiles, setTiles] = useState<string[]>([]);
  const [servedTiles] = useState<string[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: "48px 24px", position: "relative" }}>
      <Backdrop uploadUrls={tiles} servedUrls={servedTiles} />
      <h1 style={{ fontSize: "1.3rem" }}>
        <span style={{ color: "var(--primary)" }}>▲</span> {COPY.appName}
        <span className="mono" style={{ color: "var(--muted)", fontSize: "0.7rem", marginLeft: 12 }}>
          album {albumId.slice(0, 8)}
        </span>
      </h1>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 24 }}>
        <Upload albumId={albumId} onCommitted={() => setCommitted(true)} onTiles={setTiles} />
        {committed && <Progress albumId={albumId} onReady={() => setReady(true)} />}
        <Enroll onFind={(uid) => setUserId(uid)} />
        {userId && !ready && (
          <p className="mono" style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
            enrolled {userId.slice(0, 8)} · waiting for index
          </p>
        )}
        {userId && ready && <Results albumId={albumId} userId={userId} onThumbs={() => {}} />}
        <AlbumActions albumId={albumId} userId={userId} />
      </div>
    </main>
  );
}
