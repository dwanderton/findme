"use client";

import { useRef, useState } from "react";

import { commitAlbum, uploadAll, type UploadProgress } from "@/lib/api";
import { COPY } from "@/lib/copy";
import { preprocessFile, type PreppedPhoto } from "@/lib/preprocess";

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
  const [gpsFound, setGpsFound] = useState(0);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    const files = Array.from(list).filter((f) => f.type.startsWith("image/") || /\.(jpe?g|png|webp|heic)$/i.test(f.name));
    if (!files.length) return;
    setPhase("preprocessing");
    setMessage(null);
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
    setPhase("uploading");
    const result = await uploadAll(albumId, photos, setProgress);
    if (result.failed.length) {
      setPhase("error");
      setMessage(`${result.failed.length} files failed. ${COPY.uploadRetry}?`);
      return;
    }
    setPhase("committing");
    try {
      const commit = await commitAlbum(albumId, result.uploaded);
      setMessage(`${commit.accepted} photos accepted${commit.rejected.length ? `, ${commit.rejected.length} rejected` : ""}`);
      setPhase("done");
      onCommitted();
    } catch (e) {
      setPhase("error");
      setMessage(e instanceof Error ? e.message : "Commit failed.");
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
          void handleFiles(e.dataTransfer.files);
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
        {phase === "idle" ? "Drop photos or click to choose" : null}
        {phase === "preprocessing" && (
          <span className="mono log-stream">
            {COPY.uploadPreflight} {prepped} · gps found in {gpsFound}
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
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => void handleFiles(e.target.files)}
      />
    </div>
  );
}
