"use client";

import { use, useState } from "react";

import { Upload } from "@/components/Upload";
import { COPY } from "@/lib/copy";

export default function AlbumPage({ params }: { params: Promise<{ albumId: string }> }) {
  const { albumId } = use(params);
  const [committed, setCommitted] = useState(false);
  const [tiles, setTiles] = useState<string[]>([]);

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: "48px 24px", position: "relative" }}>
      <h1 style={{ fontSize: "1.3rem" }}>
        <span style={{ color: "var(--primary)" }}>▲</span> {COPY.appName}
        <span className="mono" style={{ color: "var(--muted)", fontSize: "0.7rem", marginLeft: 12 }}>
          album {albumId.slice(0, 8)}
        </span>
      </h1>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 24 }}>
        <Upload albumId={albumId} onCommitted={() => setCommitted(true)} onTiles={setTiles} />
        {committed && (
          <p className="mono" style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
            indexing started · progress UI lands next
          </p>
        )}
        {tiles.length > 0 && (
          <p className="mono" style={{ color: "var(--muted)", fontSize: "0.7rem" }}>
            {tiles.length} tiles staged for backdrop
          </p>
        )}
      </div>
    </main>
  );
}
