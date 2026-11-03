export const WARM_INTERVAL_MS = 60_000;

let lastWarmAt: number | null = null;

export function claimWarm(now = Date.now()): boolean {
  if (lastWarmAt !== null && now - lastWarmAt < WARM_INTERVAL_MS) return false;
  lastWarmAt = now;
  return true;
}

export function resetWarm() {
  lastWarmAt = null;
}

export function vlmRunUrl(openaiBase: string): string | null {
  const m = openaiBase.match(/^(https:\/\/api\.runpod\.ai\/v2\/[a-z0-9]+)\/openai\/?$/i);
  return m ? `${m[1]}/run` : null;
}
