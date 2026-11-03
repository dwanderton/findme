"use client";

import { useEffect, useRef, useState } from "react";

import { commitAlbum, uploadAll, type Rejection, type UploadProgress } from "@/lib/api";
import { COPY, rejectionLine } from "@/lib/copy";
import { filesFromDataTransfer } from "@/lib/folder";
import { STAGE_DWELL_MS } from "@/lib/pacing";
import { MAX_ALBUM_PHOTOS, preprocessFile, type PreppedPhoto } from "@/lib/preprocess";

type Phase = "idle" | "preprocessing" | "uploading" | "committing" | "done" | "error";

export function Upload({
  albumId,
  onCommitted,
  onTiles,
}: {
  albumId: string;
  onCommitted: () => void;
  onTiles?: (urls: string[]) => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [prepped, setPrepped] = useState(0);
  const [prepTotal, setPrepTotal] = useState(0);
  const [gpsFound, setGpsFound] = useState(0);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [rejected, setRejected] = useState<Rejection[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const timers = useRef<number[]>([]);
  const nextAt = useRef(0);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  function schedule(fn: () => void) {
    const now = Date.now();
    const at = Math.max(now, nextAt.current);
    nextAt.current = at + STAGE_DWELL_MS;
    timers.current.push(window.setTimeout(fn, at - now));
  }

  function failNow(msg: string) {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    nextAt.current = 0;
    setMessage(msg);
    setPhase("error");
  }

  async function handleFiles(list: File[]) {
    const files = list.filter((f) => f.type.startsWith("image/") || /\.(jpe?g|png|webp|heic|avif)$/i.test(f.name));
    if (!files.length) return;
    if (files.length > MAX_ALBUM_PHOTOS) {
      failNow(`${files.length} images selected; an album holds up to ${MAX_ALBUM_PHOTOS}.`);
      return;
    }
    nextAt.current = 0;
    setMessage(null);
    setRejected([]);
    setPrepTotal(files.length);
    schedule(() => setPhase("preprocessing"));
    const photos: PreppedPhoto[] = [];
    let gps = 0;
    const tiles: string[] = [];
    for (const f of files) {
      const p = await preprocessFile(f);
      photos.push(p);
      if (p.exif?.gps_present) gps += 1;
      setPrepped(photos.length);
      setGpsFound(gps);
      if (tiles.length < 60) {
        tiles.push(URL.createObjectURL(p.blob));
        onTiles?.([...tiles]);
      }
    }
    schedule(() => setPhase("uploading"));
    const result = await uploadAll(albumId, photos, setProgress);
    if (result.failed.length) {
      failNow(`${result.failed.length} files failed. ${COPY.uploadRetry}?`);
      return;
    }
    schedule(() => setPhase("committing"));
    try {
      const commit = await commitAlbum(albumId, result.uploaded);
      const allRejected = [...result.rejected, ...commit.rejected];
      schedule(() => {
        setMessage(`${commit.accepted} photos accepted${allRejected.length ? `, ${allRejected.length} rejected` : ""}`);
        setRejected(allRejected);
        setPhase("done");
      });
      schedule(onCommitted);
    } catch (e) {
      failNow(e instanceof Error ? e.message : "Commit failed.");
    }
  }

  return (
    <div data-testid="upload">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const pending = filesFromDataTransfer(e.dataTransfer);
          void pending.then((files) => handleFiles(files));
        }}
        style={{
          border: "1px dashed var(--border)",
          borderRadius: 8,
          padding: "36px 20px",
          textAlign: "center",
          cursor: "pointer",
          color: "var(--muted)",
        }}
      >
        {phase === "idle" ? "Drop photos or a folder, or click to choose" : null}
        {phase === "preprocessing" && (
          <span className="mono log-stream">
            {COPY.uploadPreflight} {prepped} / {prepTotal} · gps found in {gpsFound}
          </span>
        )}
        {phase === "uploading" && progress && (
          <span className="mono log-stream">
            uploading {progress.uploaded} / {progress.total} photos · {(progress.bytesSent / 1e6).toFixed(1)} MB
          </span>
        )}
        {phase === "committing" && <span className="mono">validating…</span>}
        {phase === "done" && <span className="mono" style={{ color: "var(--status-running)" }}>{message}</span>}
        {phase === "error" && <span className="mono" style={{ color: "var(--status-error)" }}>{message}</span>}
      </div>
      {phase === "done" && rejected.length > 0 && (
        <ul data-testid="rejected-list" style={{ listStyle: "none", marginTop: 8 }}>
          {rejected.slice(0, 8).map((r, i) => (
            <li key={`${r.name}-${i}`} className="mono" style={{ fontSize: "0.72rem", color: "var(--status-pending)", padding: "1px 0" }}>
              {rejectionLine(r)}
            </li>
          ))}
          {rejected.length > 8 && (
            <li className="mono" style={{ fontSize: "0.72rem", color: "var(--muted)" }}>
              and {rejected.length - 8} more
            </li>
          )}
        </ul>
      )}
      {phase === "idle" && (
        <button
          type="button"
          className="mono"
          data-testid="folder-cta"
          onClick={() => folderInputRef.current?.click()}
          style={{
            marginTop: 8,
            background: "none",
            border: "none",
            padding: 0,
            color: "var(--muted)",
            cursor: "pointer",
            textDecoration: "underline",
            fontSize: "0.72rem",
          }}
        >
          {COPY.uploadFolderCta}
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        data-testid="photo-input"
        onChange={(e) => void handleFiles(Array.from(e.target.files ?? []))}
      />
      <input
        ref={folderInputRef}
        type="file"
        multiple
        hidden
        data-testid="folder-input"
        {...{ webkitdirectory: "" }}
        onChange={(e) => void handleFiles(Array.from(e.target.files ?? []))}
      />
    </div>
  );
}
