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
import { weatherVisual } from "@/lib/weatherVisual";

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
      setExpanded((cur) => cur ?? r.matches[0]?.photoId ?? null);
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

      {expanded && resp.matches.find((x) => x.photoId === expanded) && (
        <ExpandedPanel m={resp.matches.find((x) => x.photoId === expanded)!} />
      )}

      {visible.length > 1 && (
        <>
          <div className="mono" style={{ fontSize: "0.7rem", color: "var(--muted)", letterSpacing: "0.08em" }}>
            ALL MATCHES
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 10 }}>
            {visible.map((m, i) => (
              <MatchCard key={m.photoId} m={m} index={i} expanded={expanded === m.photoId} onToggle={() => setExpanded(m.photoId)} />
            ))}
          </div>
        </>
      )}
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

function WeatherCard({ m }: { m: Match }) {
  const w = m.weather;
  if (!w.present) {
    return (
      <div className="card card-in">
        <span className="mono" style={cardLabel}>WEATHER</span>
        <p className="mono" style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{weatherLine(w)}</p>
      </div>
    );
  }
  const v = weatherVisual(w.condition, w.localTime);
  return (
    <div
      className="card-in weather-card"
      style={{
        position: "relative",
        overflow: "hidden",
        borderRadius: 10,
        border: "1px solid var(--border)",
        background: v.gradient,
        color: v.text,
        minHeight: 230,
        padding: 14,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
      }}
    >
      <div className={`wx-fx wx-${v.family}${v.night ? " wx-night" : ""}`} aria-hidden />
      <div style={{ position: "relative" }} />
      <div style={{ position: "relative" }}>
        <div className="mono" style={{ fontSize: "3rem", fontWeight: 200, lineHeight: 1 }}>
          {Math.round(w.tempC!)}°
        </div>
        <div style={{ fontSize: "1rem", marginTop: 4, textTransform: "capitalize" }}>{w.condition}</div>
        <div className="mono" style={{ fontSize: "0.72rem", opacity: 0.85, marginTop: 6 }}>
          {w.localTime ? `${w.localTime} local` : ""}
          {w.windKmh ? ` · wind ${w.windKmh} km/h` : ""}
        </div>
      </div>
    </div>
  );
}

function LocationCard({ m }: { m: Match }) {
  const [mapsDown, setMapsDown] = useState(false);
  const hasMap = m.place.present && typeof m.place.lat === "number" && typeof m.place.lon === "number";
  if (!hasMap) {
    return (
      <div className="card card-in" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: 230 }}>
        <p className="mono" style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{placeLine(m.place)}</p>
      </div>
    );
  }
  const d = 0.004;
  const osmSrc = `https://www.openstreetmap.org/export/embed.html?bbox=${m.place.lon! - d},${m.place.lat! - d},${m.place.lon! + d},${m.place.lat! + d}&layer=mapnik&marker=${m.place.lat},${m.place.lon}`;
  const mapSrc = `/api/staticmap?lat=${m.place.lat}&lon=${m.place.lon}&zoom=14`;
  return (
    <div className="card-in" style={{ position: "relative", overflow: "hidden", borderRadius: 10, border: "1px solid var(--border)", minHeight: 230 }}>
      {mapsDown ? (
        <iframe
          src={osmSrc}
          title={`map of ${m.place.label ?? "location"}`}
          style={{ width: "100%", height: "100%", minHeight: 230, border: 0, display: "block" }}
        />
      ) : (
        <img
          src={mapSrc}
          alt={`map of ${m.place.label ?? "location"}`}
          onError={() => setMapsDown(true)}
          style={{ width: "100%", height: "100%", minHeight: 230, objectFit: "cover", display: "block" }}
        />
      )}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          padding: "20px 12px 10px",
          background: "linear-gradient(180deg, transparent, oklch(0.13 0.05 291 / 0.85))",
          pointerEvents: "none",
        }}
      >
        <p className="mono" style={{ fontSize: "0.76rem", color: "var(--text)" }}>{m.place.label}</p>
      </div>
    </div>
  );
}

function ExpandedPanel({ m }: { m: Match }) {
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

      <WeatherCard m={m} />

      <LocationCard m={m} />

      <div className="card card-in" style={{ minHeight: 230, display: "flex", flexDirection: "column", justifyContent: "center" }}>
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
