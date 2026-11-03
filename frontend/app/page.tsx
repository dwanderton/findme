"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DebugConsole } from "@/components/DebugConsole";
import { createAlbum } from "@/lib/api";
import { COPY } from "@/lib/copy";
import { installFetchInterceptor } from "@/lib/debugLog";

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      style={{ color: "var(--primary-text)", textDecoration: "underline", textUnderlineOffset: 2 }}
    >
      {children}
    </a>
  );
}

const FEATURES: [string, React.ReactNode][] = [
  [
    "FACE SEARCH",
    <>
      <Ext href="https://github.com/deepinsight/insightface/tree/master/detection/scrfd">SCRFD</Ext> +{" "}
      <Ext href="https://arxiv.org/abs/1801.07698">ArcFace</Ext> on{" "}
      <Ext href="https://docs.runpod.io/serverless/overview">Runpod serverless</Ext> GPUs. Upload a selfie, find every
      photo you are in.
    </>,
  ],
  [
    "LOCATION",
    <>
      EXIF GPS resolved to a place with{" "}
      <Ext href="https://developers.google.com/maps/documentation/geocoding">Google Geocoding</Ext> and plotted on a{" "}
      <Ext href="https://developers.google.com/maps/documentation/maps-static">Google Static Map</Ext> for each match.
    </>,
  ],
  [
    "WEATHER",
    <>
      The conditions at the moment each photo was taken, from <Ext href="https://open-meteo.com">Open-Meteo</Ext>.
    </>,
  ],
  [
    "CAPTIONS",
    <>
      <Ext href="https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct-AWQ">Qwen2.5-VL</Ext> writes a caption and tags for
      every match.
    </>,
  ],
  [
    "RUNPOD",
    <>
      A load-balanced <Ext href="https://www.runpod.io">Runpod</Ext> GPU endpoint for face detection, embedding, and
      the map proxy, plus a queue endpoint serving the VLM.
    </>,
  ],
  [
    "FRONTEND",
    <>
      A <Ext href="https://nextjs.org">Next.js</Ext> app on <Ext href="https://vercel.com">Vercel</Ext> proxies every
      request to Runpod: it injects the API key server-side, rate-limits per IP, and relays indexing progress over
      SSE.
    </>,
  ],
];

export default function Home() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    installFetchInterceptor();
    void fetch("/api/warmup", { method: "POST" }).catch(() => {});
  }, []);

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
      <DebugConsole />
      <div className="card card-in" style={{ padding: "32px 28px", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1 style={{ fontSize: "2rem", letterSpacing: "-0.02em" }}>
              <span className="logo-dot" aria-hidden /> {COPY.appName}
            </h1>
            <p style={{ color: "var(--muted)", marginTop: 10, fontSize: "1.05rem" }}>{COPY.tagline}</p>
          </div>
          <button
            className="primary"
            onClick={start}
            disabled={busy}
            aria-label="Create an album"
            title="Create an album"
            style={{
              width: 52,
              height: 52,
              borderRadius: "50%",
              padding: 0,
              flexShrink: 0,
              display: "grid",
              placeItems: "center",
            }}
          >
            {busy ? (
              <span className="dot running" style={{ background: "#fff" }} />
            ) : (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
              </svg>
            )}
          </button>
        </div>
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
        face search on Runpod serverless
      </p>
    </main>
  );
}
