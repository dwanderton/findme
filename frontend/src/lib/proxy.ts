import { take } from "./ratelimit";

export const BACKEND_URL = () => process.env.BACKEND_URL ?? "http://localhost:8000";

const FORWARD_HEADERS = ["content-type", "x-owner-token"];

export function limitKind(path: string): "enroll" | "places" | "default" {
  if (path.startsWith("enroll")) return "enroll";
  if (path.startsWith("places")) return "places";
  return "default";
}

export function rateLimitResponse(retryAfterS: number): Response {
  return Response.json(
    {
      error: {
        code: "RATE_LIMITED",
        message: `Too many requests. Retry in ${retryAfterS}s.`,
        retryable: true,
      },
    },
    { status: 429, headers: { "Retry-After": String(retryAfterS) } },
  );
}

export async function forward(req: Request, path: string): Promise<Response> {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "local";
  const gate = take(ip, limitKind(path));
  if (!gate.ok) return rateLimitResponse(gate.retryAfterS);

  const url = new URL(req.url);
  const target = `${BACKEND_URL()}/${path}${url.search}`;
  const headers = new Headers();
  for (const h of FORWARD_HEADERS) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  const runpodKey = process.env.RUNPOD_API_KEY;
  if (runpodKey) headers.set("authorization", `Bearer ${runpodKey}`);

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : req.body,
      // @ts-expect-error node fetch streaming body
      duplex: "half",
    });
  } catch {
    return Response.json(
      { error: { code: "UPSTREAM_FACE_ENGINE", message: "Backend unreachable.", retryable: true } },
      { status: 502 },
    );
  }

  const respHeaders = new Headers();
  for (const h of ["content-type", "x-parts", "content-disposition", "cache-control", "retry-after"]) {
    const v = upstream.headers.get(h);
    if (v) respHeaders.set(h, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
}
