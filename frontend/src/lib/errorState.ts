export type UiErrorKind = "rate-limited" | "cold-start" | "offline" | "validation" | "not-ready" | "upstream" | "unknown";

export type UiError = {
  kind: UiErrorKind;
  message: string;
  retryAfterS: number | null;
  retryable: boolean;
};

export function classify(status: number, code: string | undefined, retryAfterHeader: string | null, online = true): UiError {
  if (!online) return { kind: "offline", message: "Connection lost. Retrying when back online.", retryAfterS: null, retryable: true };
  const retryAfterS = retryAfterHeader ? Number(retryAfterHeader) || null : null;
  switch (code) {
    case "RATE_LIMITED":
      return { kind: "rate-limited", message: "Too many requests.", retryAfterS: retryAfterS ?? 30, retryable: true };
    case "COLD_START":
      return { kind: "cold-start", message: "GPU worker starting.", retryAfterS: retryAfterS ?? 10, retryable: true };
    case "INDEX_NOT_READY":
      return { kind: "not-ready", message: "Index still building.", retryAfterS: 2, retryable: true };
    case "NO_FACE_IN_SELFIE":
    case "UNSUPPORTED_MEDIA":
    case "TOO_MANY_SELFIES":
    case "BODY_TOO_LARGE":
      return { kind: "validation", message: "", retryAfterS: null, retryable: false };
  }
  if (status === 429) return { kind: "rate-limited", message: "Too many requests.", retryAfterS: retryAfterS ?? 30, retryable: true };
  if (status === 503) return { kind: "cold-start", message: "GPU worker starting.", retryAfterS: retryAfterS ?? 10, retryable: true };
  if (status >= 500) return { kind: "upstream", message: "Backend failed. Retry.", retryAfterS: null, retryable: true };
  return { kind: "unknown", message: `Request failed (${status}).`, retryAfterS: null, retryable: false };
}

export function countdown(start: number, elapsedS: number): number {
  return Math.max(0, Math.ceil(start - elapsedS));
}

export type QueuedRetry = { run: () => void };

export class OfflineQueue {
  private queue: QueuedRetry[] = [];

  enqueue(r: QueuedRetry) {
    this.queue.push(r);
  }

  flush(): number {
    const n = this.queue.length;
    for (const r of this.queue.splice(0)) r.run();
    return n;
  }

  get size() {
    return this.queue.length;
  }
}
