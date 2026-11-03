"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createAlbum } from "@/lib/api";
import { COPY } from "@/lib/copy";

export default function Home() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const album = await createAlbum(1);
      localStorage.setItem(`owner:${album.albumId}`, album.ownerToken);
      router.push(`/a/${album.albumId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something failed.");
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 560, margin: "0 auto", padding: "96px 24px" }}>
      <h1 style={{ fontSize: "1.6rem" }}>
        <span style={{ color: "var(--primary)" }}>▲</span> {COPY.appName}
      </h1>
      <p style={{ color: "var(--muted)", margin: "8px 0 32px" }}>{COPY.tagline}</p>
      <button className="primary" onClick={start} disabled={busy}>
        {busy ? "creating album…" : "Create an album"}
      </button>
      {error && (
        <p className="mono" style={{ color: "var(--status-error)", marginTop: 16, fontSize: "0.8rem" }}>
          {error}
        </p>
      )}
      <p className="mono" style={{ color: "var(--muted)", marginTop: 48, fontSize: "0.7rem" }}>
        face search on Runpod serverless · enrichment by Google Geocoding + Open-Meteo
      </p>
    </main>
  );
}
