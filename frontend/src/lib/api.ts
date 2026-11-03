import type { PreppedPhoto } from "./preprocess";
import { planBatches } from "./preprocess";

export type Rejection = { name: string; reason: string };

export type UploadProgress = {
  uploaded: number;
  total: number;
  bytesSent: number;
  failed: string[];
  rejected: Rejection[];
};

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api/${path}`, init);
  const body = await r.json().catch(() => null);
  if (!r.ok) {
    const err = body?.error ?? { code: "UNKNOWN", message: `HTTP ${r.status}`, retryable: false };
    const { reportApiError } = await import("@/components/Banners");
    reportApiError(r.status, err.code, r.headers.get("retry-after"));
    throw Object.assign(new Error(err.message), { code: err.code, status: r.status, retryable: err.retryable, retryAfter: r.headers.get("retry-after") });
  }
  return body as T;
}

export async function createAlbum(photoCount: number) {
  return apiJson<{ albumId: string; ownerToken: string; upload: { url: string } }>("albums", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ photoCount }),
  });
}

async function sendBatch(albumId: string, batch: PreppedPhoto[], attempt = 0): Promise<Rejection[]> {
  const form = new FormData();
  form.set("albumId", albumId);
  batch.forEach((p, i) => {
    form.append(`p${i}`, p.blob, p.name);
    if (p.exif) form.set(`exif_p${i}`, JSON.stringify(p.exif));
  });
  const r = await fetch("/api/upload", { method: "POST", body: form });
  if (!r.ok) {
    if (attempt < 2) return sendBatch(albumId, batch, attempt + 1);
    throw new Error(`batch failed: HTTP ${r.status}`);
  }
  const body = await r.json().catch(() => null);
  return (body?.rejected as Rejection[] | undefined) ?? [];
}

export async function uploadAll(
  albumId: string,
  photos: PreppedPhoto[],
  onProgress: (p: UploadProgress) => void,
  concurrency = 6,
): Promise<UploadProgress> {
  const batches = planBatches(photos);
  const state: UploadProgress = { uploaded: 0, total: photos.length, bytesSent: 0, failed: [], rejected: [] };
  let next = 0;
  async function worker() {
    while (next < batches.length) {
      const batch = batches[next++];
      try {
        const rejected = await sendBatch(albumId, batch);
        state.rejected.push(...rejected);
        state.uploaded += batch.length;
        state.bytesSent += batch.reduce((s, p) => s + p.blob.size, 0);
      } catch {
        state.failed.push(...batch.map((p) => p.name));
      }
      onProgress({ ...state });
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, batches.length) }, worker));
  return state;
}

export async function commitAlbum(albumId: string, uploaded: number) {
  return apiJson<{ accepted: number; rejected: { name: string; reason: string }[] }>(
    `albums/${albumId}/commit`,
    { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ uploaded }) },
  );
}
