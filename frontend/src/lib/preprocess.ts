export type ClientExif = {
  gps_present: boolean;
  lat?: number;
  lon?: number;
  taken_at?: string;
  make?: string;
  model?: string;
  lens?: string;
  focal_length_mm?: number;
  aperture?: number;
  shutter?: string;
  iso?: number;
};

export type PreppedPhoto = { name: string; blob: Blob; exif: ClientExif | null };

export const BATCH_MAX_PHOTOS = 8;
export const BATCH_MAX_BYTES = 8_000_000;
export const RESIZE_PX = 2048;
export const JPEG_QUALITY = 0.85;

export function planBatches<T extends { blob: { size: number } }>(items: T[]): T[][] {
  const batches: T[][] = [];
  let current: T[] = [];
  let size = 0;
  for (const item of items) {
    const overCount = current.length >= BATCH_MAX_PHOTOS;
    const overBytes = current.length > 0 && size + item.blob.size > BATCH_MAX_BYTES;
    if (overCount || overBytes) {
      batches.push(current);
      current = [];
      size = 0;
    }
    current.push(item);
    size += item.blob.size;
  }
  if (current.length) batches.push(current);
  return batches;
}

export function normalizeExif(raw: Record<string, unknown> | null | undefined): ClientExif | null {
  if (!raw) return null;
  const lat = typeof raw.latitude === "number" ? raw.latitude : undefined;
  const lon = typeof raw.longitude === "number" ? raw.longitude : undefined;
  const dt = raw.DateTimeOriginal instanceof Date ? raw.DateTimeOriginal : undefined;
  const exif: ClientExif = {
    gps_present: lat !== undefined && lon !== undefined,
    lat,
    lon,
    taken_at: dt ? dt.toISOString().slice(0, 19) : undefined,
    make: typeof raw.Make === "string" ? raw.Make : undefined,
    model: typeof raw.Model === "string" ? raw.Model : undefined,
    lens: typeof raw.LensModel === "string" ? raw.LensModel : undefined,
    focal_length_mm: typeof raw.FocalLength === "number" ? raw.FocalLength : undefined,
    aperture: typeof raw.FNumber === "number" ? raw.FNumber : undefined,
    iso: typeof raw.ISO === "number" ? raw.ISO : undefined,
    shutter:
      typeof raw.ExposureTime === "number" && raw.ExposureTime > 0
        ? raw.ExposureTime >= 1
          ? `${raw.ExposureTime}s`
          : `1/${Math.round(1 / raw.ExposureTime)}`
        : undefined,
  };
  const empty = !exif.gps_present && !exif.taken_at && !exif.make;
  return empty ? null : exif;
}

export async function preprocessFile(file: File): Promise<PreppedPhoto> {
  let exif: ClientExif | null = null;
  try {
    const exifr = (await import("exifr")).default;
    exif = normalizeExif(await exifr.parse(file, { gps: true, exif: true }));
  } catch {
    exif = null;
  }
  const blob = await resizeToJpeg(file);
  return { name: file.name, blob, exif };
}

async function resizeToJpeg(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) return file;
  const scale = Math.min(1, RESIZE_PX / Math.max(bitmap.width, bitmap.height));
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return file;
  ctx.drawImage(bitmap, 0, 0, w, h);
  return await new Promise<Blob>((resolve) =>
    canvas.toBlob((b) => resolve(b ?? file), "image/jpeg", JPEG_QUALITY),
  );
}
