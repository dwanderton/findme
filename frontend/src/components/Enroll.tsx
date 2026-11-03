"use client";

import { useReducer, useRef } from "react";

import { COPY } from "@/lib/copy";
import { canAddMore, canFind, enrollReducer, initialEnroll } from "@/lib/enrollState";
import { preprocessFile } from "@/lib/preprocess";

export function Enroll({ onFind }: { onFind: (userId: string) => void }) {
  const [state, dispatch] = useReducer(enrollReducer, initialEnroll);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(list: FileList | null) {
    if (!list?.length) return;
    const files = Array.from(list).slice(0, 5);
    dispatch({ type: "submit", names: files.map((f) => f.name) });
    const form = new FormData();
    for (let i = 0; i < files.length; i++) {
      const p = await preprocessFile(files[i]);
      form.append(`s${i}`, p.blob, p.name);
    }
    const isAppend = state.userId !== null;
    if (isAppend) form.set("userId", state.userId!);
    const r = await fetch("/api/enroll", { method: isAppend ? "PATCH" : "POST", body: form });
    const body = await r.json().catch(() => null);
    if (!r.ok) {
      dispatch({ type: "failure", message: body?.error?.message ?? COPY.noFace, selfie: body?.error?.selfie });
      return;
    }
    dispatch({ type: "success", userId: body.userId, faces: body.faces });
  }

  return (
    <div data-testid="enroll">
      <div
        role="button"
        tabIndex={0}
        onClick={() => canAddMore(state) && inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && canAddMore(state) && inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (canAddMore(state)) void handleFiles(e.dataTransfer.files);
        }}
        style={{
          border: "1px dashed var(--border)",
          borderRadius: 8,
          padding: "28px 20px",
          textAlign: "center",
          color: "var(--muted)",
          cursor: canAddMore(state) ? "pointer" : "default",
        }}
      >
        {state.chips.length === 0 ? COPY.enrollDrop : COPY.enrollMore}
      </div>
      <input ref={inputRef} type="file" accept="image/*" multiple hidden onChange={(e) => void handleFiles(e.target.files)} />

      {state.chips.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          {state.chips.map((c, i) => (
            <span key={`${c.name}-${i}`} className={`chip log-stream ${c.state === "ok" ? "active" : ""}`}>
              {c.state === "checking" && (
                <>
                  <span className="dot pending" /> {COPY.checkingFace}
                </>
              )}
              {c.state === "ok" && (
                <>
                  <span className="dot running" style={{ animation: "none" }} /> face {c.facePx}px
                  {c.multipleFaces ? " · largest used" : ""}
                </>
              )}
              {c.state === "failed" && (
                <>
                  <span className="dot error" /> {c.error ?? COPY.noFace}
                </>
              )}
            </span>
          ))}
        </div>
      )}

      <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
        <button className="primary" disabled={!canFind(state)} onClick={() => state.userId && onFind(state.userId)}>
          {COPY.enrollCta}
        </button>
        {state.error && (
          <span className="mono" style={{ color: "var(--status-error)", fontSize: "0.75rem" }}>
            {state.error}
          </span>
        )}
      </div>
    </div>
  );
}
