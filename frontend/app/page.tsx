"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createAlbum } from "@/lib/api";
import { COPY } from "@/lib/copy";

const FEATURES = [
  ["FACE SEARCH", "SCRFD + ArcFace on Runpod serverless GPUs. Upload a selfie, find every photo you are in."],
  ["LOCATION", "EXIF GPS resolved to a place and plotted on a map for each match."],
  ["WEATHER", "The conditions at the moment each photo was taken, from Open-Meteo."],
  ["CAPTIONS", "Qwen2.5-VL writes a caption and tags for every match."],
];

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
    <main style={{ maxWidth: 820, margin: "0 auto", padding: "80px 24px", position: "relative", zIndex: 1 }}>
      <div className="card card-in" style={{ padding: "32px 28px", marginBottom: 16 }}>
        <h1 style={{ fontSize: "2rem", letterSpacing: "-0.02em" }}>
          <span style={{ color: "var(--primary)" }}>▲</span> {COPY.appName}
        </h1>
        <p style={{ color: "var(--muted)", margin: "10px 0 24px", fontSize: "1.05rem" }}>{COPY.tagline}</p>
        <button className="primary" onClick={start} disabled={busy} style={{ fontSize: "1rem", padding: "11px 24px" }}>
          {busy ? "creating album…" : "Create an album"}
        </button>
        {error && (
          <p className="mono" style={{ color: "var(--status-error)", marginTop: 16, fontSize: "0.8rem" }}>
            {error}
          </p>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        {FEATURES.map(([label, body], i) => (
          <div key={label} className="card card-in" style={{ animationDelay: `${i * 60}ms` }}>
            <span className="mono" style={{ fontSize: "0.62rem", letterSpacing: "0.1em", color: "var(--primary-text)" }}>{label}</span>
            <p style={{ fontSize: "0.85rem", marginTop: 8, color: "var(--text)" }}>{body}</p>
          </div>
        ))}
      </div>

      <p className="mono" style={{ color: "var(--muted)", marginTop: 28, fontSize: "0.68rem", textAlign: "center" }}>
        face search on Runpod serverless · Google Geocoding + Open-Meteo · Qwen2.5-VL captions
      </p>
    </main>
  );
}
