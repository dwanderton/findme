type Bucket = { tokens: number; last: number };

const buckets = new Map<string, Bucket>();

export const LIMITS: Record<string, { perMin: number }> = {
  default: { perMin: 30 },
  enroll: { perMin: 5 },
};

export function take(ip: string, kind: keyof typeof LIMITS = "default", now = Date.now()): { ok: boolean; retryAfterS: number; remaining: number } {
  const limit = LIMITS[kind] ?? LIMITS.default;
  const key = `${ip}:${kind}`;
  const b = buckets.get(key) ?? { tokens: limit.perMin, last: now };
  const refill = ((now - b.last) / 60_000) * limit.perMin;
  b.tokens = Math.min(limit.perMin, b.tokens + refill);
  b.last = now;
  if (b.tokens < 1) {
    buckets.set(key, b);
    const retryAfterS = Math.ceil(((1 - b.tokens) / limit.perMin) * 60);
    return { ok: false, retryAfterS, remaining: 0 };
  }
  b.tokens -= 1;
  buckets.set(key, b);
  return { ok: true, retryAfterS: 0, remaining: Math.floor(b.tokens) };
}

export function resetBuckets() {
  buckets.clear();
}
