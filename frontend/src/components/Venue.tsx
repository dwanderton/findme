"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { COPY } from "@/lib/copy";
import { debounce } from "@/lib/debounce";

type Suggestion = { placeId: string; label: string };
type Venue = { label: string; lat: number; lon: number; source: string };

export function VenueLink({ albumId, venue, onChange }: { albumId: string; venue: Venue | null; onChange: (v: Venue | null) => void }) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [highlight, setHighlight] = useState(0);
  const [degraded, setDegraded] = useState(false);
  const [busy, setBusy] = useState(false);
  const session = useRef(crypto.randomUUID());
  const [owner, setOwner] = useState<string | null>(null);

  useEffect(() => {
    setOwner(localStorage.getItem(`owner:${albumId}`));
  }, [albumId]);

  const lookup = useMemo(
    () =>
      debounce(async (q: string) => {
        if (q.length < 3) {
          setSuggestions([]);
          return;
        }
        try {
          const r = await fetch(`/api/places/autocomplete?q=${encodeURIComponent(q)}&session=${session.current}&albumId=${albumId}`);
          const body = await r.json();
          setDegraded(Boolean(body.degraded));
          setSuggestions(body.suggestions ?? []);
          setHighlight(0);
        } catch {
          setDegraded(true);
          setSuggestions([]);
        }
      }, 300),
    [albumId],
  );

  async function select(s: Suggestion) {
    if (!owner) return;
    setBusy(true);
    setSuggestions([]);
    const r = await fetch(`/api/albums/${albumId}/venue`, {
      method: "PATCH",
      headers: { "content-type": "application/json", "x-owner-token": owner },
      body: JSON.stringify({ placeId: s.placeId, session: session.current }),
    });
    const body = await r.json().catch(() => null);
    setBusy(false);
    if (r.ok) {
      onChange(body.venue);
      setQuery("");
    } else {
      setDegraded(true);
    }
  }

  async function unlink() {
    if (!owner) return;
    await fetch(`/api/albums/${albumId}/venue`, { method: "DELETE", headers: { "x-owner-token": owner } });
    onChange(null);
  }

  if (!owner) return null;

  if (venue) {
    return (
      <div className="chip active" data-testid="venue-chip">
        venue {venue.label}
        <button className="mono" style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer" }} onClick={() => void unlink()}>
          unlink
        </button>
      </div>
    );
  }

  return (
    <div className="card" data-testid="venue-link">
      <p className="mono" style={{ fontSize: "0.78rem", color: "var(--muted)", marginBottom: 8 }}>{COPY.venuePrompt}</p>
      <input
        value={query}
        disabled={busy}
        placeholder="search a venue"
        onChange={(e) => {
          setQuery(e.target.value);
          lookup(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setHighlight((h) => Math.min(h + 1, suggestions.length - 1));
          if (e.key === "ArrowUp") setHighlight((h) => Math.max(h - 1, 0));
          if (e.key === "Enter" && suggestions[highlight]) void select(suggestions[highlight]);
        }}
        style={{
          width: "100%",
          background: "var(--surface-2)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          padding: "8px 10px",
          color: "var(--text)",
          fontFamily: "var(--sans)",
        }}
      />
      {degraded && <p className="mono" style={{ color: "var(--status-pending)", fontSize: "0.72rem", marginTop: 6 }}>{COPY.venueUnavailable}</p>}
      {suggestions.length > 0 && (
        <ul style={{ listStyle: "none", marginTop: 6 }}>
          {suggestions.map((s, i) => (
            <li key={s.placeId}>
              <button
                className="mono"
                onClick={() => void select(s)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "6px 8px",
                  fontSize: "0.78rem",
                  background: i === highlight ? "var(--primary-soft)" : "transparent",
                  border: "none",
                  color: "var(--text)",
                  cursor: "pointer",
                  borderRadius: 4,
                }}
              >
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
