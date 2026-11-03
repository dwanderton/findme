import { BACKEND_URL } from "@/lib/proxy";
import { claimWarm, vlmRunUrl } from "@/lib/warmup";

// A cold LB worker takes ~10-30 s to answer /ping; keep the function alive for it.
export const maxDuration = 60;

export async function POST() {
  const requestId = crypto.randomUUID();
  if (!claimWarm()) {
    return Response.json({ status: "already-warm" }, { headers: { "x-request-id": requestId } });
  }

  const key = process.env.RUNPOD_API_KEY;
  const auth: Record<string, string> = key ? { authorization: `Bearer ${key}` } : {};

  // The request id marks this ping as user-initiated so the backend traces it
  // (anonymous health-check pings are filtered as noise).
  const api = fetch(`${BACKEND_URL()}/ping`, { headers: { ...auth, "x-request-id": requestId }, cache: "no-store" })
    .then((r) => r.ok)
    .catch(() => false);

  // One-token generation submitted async to the queue endpoint: /run returns
  // immediately, the scale-up it triggers is the warmup.
  const runUrl = process.env.VLM_BASE_URL ? vlmRunUrl(process.env.VLM_BASE_URL) : null;
  const vlm = runUrl
    ? fetch(runUrl, {
        method: "POST",
        headers: { ...auth, "content-type": "application/json" },
        body: JSON.stringify({ input: { prompt: "ok", sampling_params: { max_tokens: 1 } } }),
        cache: "no-store",
      })
        .then((r) => r.ok)
        .catch(() => false)
    : Promise.resolve(false);

  const [apiOk, vlmOk] = await Promise.all([api, vlm]);
  return Response.json({ status: "warming", api: apiOk, vlm: vlmOk }, { headers: { "x-request-id": requestId } });
}
