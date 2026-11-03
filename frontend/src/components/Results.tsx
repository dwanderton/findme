"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiJson } from "@/lib/api";
import { COPY } from "@/lib/copy";
import {
  altText,
  cameraLine,
  filterMatches,
  photoLine,
  placeLine,
  shouldRepollVlm,
  tagCounts,
  weatherLine,
  type FindResponse,
  type Match,
} from "@/lib/results";

export function Results({ albumId, userId, onThumbs }: { albumId: string; userId: string; onThumbs?: (urls: string[]) => void }) {
  const onThumbsRef = useRef(onThumbs);
  onThumbsRef.current = onThumbs;
  const [resp, setResp] = useState<FindResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [band, setBand] = useState<"strong" | "all">("all");
  const [tags, setTags] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const attempts = useRef(0);

  const load = useCallback(async () => {
    try {
      const r = await apiJson<FindResponse>(`find?userId=${userId}&albumId=${albumId}&threshold=possible`);
      setResp(r);
      setError(null);
      onThumbsRef.current?.(r.matches.map((m) => `/api${m.thumbUrl}`));
      if (shouldRepollVlm(r, attempts.current)) {
        attempts.current += 1;
        setTimeout(load, 2000 + attempts.current * 500);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "find failed");
    }
  }, [albumId, userId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error)
    return (
      <div className="card">
        <p className="mono" style={{ color: "var(--status-error)", fontSize: "0.8rem" }}>{error}</p>
        <button className="ghost" style={{ marginTop: 10 }} onClick={() => void load()}>retry</button>
      </div>
    );
  if (!resp) return <div className="card mono" style={{ color: "var(--muted)" }}>searching…</div>;

  const visible = filterMatches(resp.matches, band, tags);
  const strongCount = resp.matches.filter((m) => m.band === "strong").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }} data-testid="results">
      <div className="mono" style={{ fontSize: "0.85rem" }}>
        you appear in <b>{resp.matches.length}</b> of {resp.album.photos} photos · {strongCount} strong ·{" "}
        {resp.matches.length - strongCount} possible
      </div>

      {resp.story.status === "ready" && resp.story.text && (
        <div className="card card-in">
          <div className="mono" style={{ fontSize: "0.65rem", letterSpacing: "0.08em", color: "var(--primary-text)" }}>{COPY.storyLabel}</div>
          <p style={{ marginTop: 6, fontSize: "0.92rem" }}>{resp.story.text}</p>
        </div>
      )}
      {resp.story.status === "pending" && (
        <div className="mono log-stream" style={{ color: "var(--muted)", fontSize: "0.75rem" }}>story generating…</div>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        <button className={`chip ${band === "all" ? "active" : ""}`} onClick={() => setBand("all")}>all bands</button>
        <button className={`chip ${band === "strong" ? "active" : ""}`} onClick={() => setBand("strong")}>strong only</button>
        {tagCounts(resp.matches).map(([t, n]) => (
          <button
            key={t}
            className={`chip ${tags.includes(t) ? "active" : ""}`}
            onClick={() => setTags((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]))}
          >
            {t} · {n}
          </button>
        ))}
      </div>

      {visible.length === 0 && (
        <div className="card mono" style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
          {band === "strong" && resp.matches.length > 0
            ? `${COPY.emptyStrong} ${resp.matches.length} ${COPY.emptyOfferPossible}`
            : "no matches in this album"}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 10 }}>
        {visible.map((m, i) => (
          <MatchCard key={m.photoId} m={m} index={i} expanded={expanded === m.photoId} onToggle={() => setExpanded(expanded === m.photoId ? null : m.photoId)} />
        ))}
      </div>

      {expanded && <ExpandedPanel m={resp.matches.find((x) => x.photoId === expanded)!} />}
    </div>
  );
}

function MatchCard({ m, index, expanded, onToggle }: { m: Match; index: number; expanded: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className="card card-in"
      style={{ padding: 6, cursor: "pointer", textAlign: "left", animationDelay: `${Math.min(index, 12) * 40}ms`, borderColor: expanded ? "var(--primary)" : undefined }}
    >
      <img src={`/api${m.thumbUrl}`} alt={altText(m)} style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: 6 }} />
      <div className="mono" style={{ fontSize: "0.68rem", marginTop: 6, display: "flex", justifyContent: "space-between" }}>
        <span style={{ color: m.band === "strong" ? "var(--status-running)" : "var(--status-pending)" }}>{m.band}</span>
        <span>{m.score.toFixed(2)}</span>
      </div>
    </button>
  );
}

const cardLabel: React.CSSProperties = {
  fontSize: "0.62rem",
  letterSpacing: "0.1em",
  color: "var(--primary-text)",
  display: "block",
  marginBottom: 8,
};

function ExpandedPanel({ m }: { m: Match }) {
  const hasMap = m.place.present && typeof m.place.lat === "number" && typeof m.place.lon === "number";
  const d = 0.004;
  const mapSrc = hasMap
    ? `https://www.openstreetmap.org/export/embed.html?bbox=${m.place.lon! - d},${m.place.lat! - d},${m.place.lon! + d},${m.place.lat! + d}&layer=mapnik&marker=${m.place.lat},${m.place.lon}`
    : null;
  return (
    <div
      data-testid="panel"
      style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 10 }}
    >
      <div className="card card-in" style={{ gridColumn: "1 / -1" }}>
        <span className="mono" style={cardLabel}>PHOTO</span>
        <img src={`/api${m.fullUrl}`} alt={altText(m)} style={{ width: "100%", maxHeight: 420, objectFit: "contain", borderRadius: 6 }} />
        <p className="mono" style={{ fontSize: "0.78rem", marginTop: 8 }}>{photoLine(m.vlm)}</p>
        {(m.vlm.tags?.length ?? 0) > 0 && (
          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
            {m.vlm.tags!.map((t) => (
              <span key={t} className="chip">{t}</span>
            ))}
          </div>
        )}
      </div>

      <div className="card card-in">
        <span className="mono" style={cardLabel}>WEATHER</span>
        <p className="mono" style={{ fontSize: "0.8rem" }}>{weatherLine(m.weather)}</p>
        {m.weather.present && (
          <p className="mono" style={{ fontSize: "1.6rem", marginTop: 6 }}>{m.weather.tempC}°C</p>
        )}
      </div>

      <div className="card card-in">
        <span className="mono" style={cardLabel}>LOCATION</span>
        {mapSrc ? (
          <>
            <iframe
              title="map"
              src={mapSrc}
              style={{ width: "100%", height: 150, border: "1px solid var(--border)", borderRadius: 6, filter: "invert(0.88) hue-rotate(200deg) saturate(0.6)" }}
            />
            <p className="mono" style={{ fontSize: "0.74rem", marginTop: 6 }}>{placeLine(m.place)}</p>
          </>
        ) : (
          <p className="mono" style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{placeLine(m.place)}</p>
        )}
      </div>

      <div className="card card-in">
        <span className="mono" style={cardLabel}>CAMERA</span>
        <p className="mono" style={{ fontSize: "0.8rem" }}>{cameraLine(m.camera)}</p>
        <p className="mono" style={{ fontSize: "0.72rem", color: "var(--muted)", marginTop: 8 }}>
          {m.takenAt ? `taken ${m.takenAt.slice(0, 10)} · ` : ""}match {m.band} · score {m.score.toFixed(2)}
        </p>
      </div>
    </div>
  );
}

export function AlbumActions({ albumId, userId, ready }: { albumId: string; userId: string | null; ready: boolean }) {
  const [copied, setCopied] = useState(false);
  const [owner, setOwner] = useState<string | null>(null);

  useEffect(() => {
    setOwner(localStorage.getItem(`owner:${albumId}`));
  }, [albumId]);

  async function remove() {
    if (!owner || !confirm(COPY.deleteConfirm)) return;
    await fetch(`/api/albums/${albumId}`, { method: "DELETE", headers: { "x-owner-token": owner } });
    window.location.href = "/";
  }

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      <button
        className="ghost"
        onClick={() => {
          void navigator.clipboard.writeText(window.location.href);
          setCopied(true);
        }}
      >
        {copied ? "link copied" : "copy share link"}
      </button>
      {userId && ready && (
        <a className="ghost" href={`/api/albums/${albumId}/download?userId=${userId}`}>
          download matches
        </a>
      )}
      {owner && (
        <button className="ghost" style={{ color: "var(--status-error)" }} onClick={() => void remove()}>
          delete everything
        </button>
      )}
      <span className="mono" style={{ color: "var(--muted)", fontSize: "0.68rem" }}>{COPY.shareDisclosure}</span>
    </div>
  );
}
