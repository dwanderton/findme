export type ClientEvent = {
  seq: number;
  ts: number;
  src: "client";
  level: "info" | "warn" | "error";
  event: string;
  requestId?: string;
  data: Record<string, unknown>;
};

export const RING_CAP = 500;

const ring: ClientEvent[] = [];
let seq = 0;
let installed = false;

export function clientEvents(): ClientEvent[] {
  return [...ring];
}

export function pushClientEvent(event: string, level: ClientEvent["level"], data: Record<string, unknown>, requestId?: string) {
  seq += 1;
  ring.push({ seq, ts: Date.now(), src: "client", level, event, data, requestId });
  if (ring.length > RING_CAP) ring.shift();
}

export function resetClientEvents() {
  ring.length = 0;
  seq = 0;
}

export function installFetchInterceptor() {
  if (installed || typeof window === "undefined") return;
  installed = true;
  const orig = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    if (!url.startsWith("/api") || url.startsWith("/api/debug")) return orig(input, init);
    const started = performance.now();
    try {
      const resp = await orig(input, init);
      const requestId = resp.headers.get("x-request-id") ?? undefined;
      const data: Record<string, unknown> = {
        method: init?.method ?? "GET",
        path: url.split("?")[0],
        status: resp.status,
        ms: Math.round(performance.now() - started),
      };
      if (url.startsWith("/api/warmup")) {
        try {
          Object.assign(data, await resp.clone().json());
        } catch {}
      }
      pushClientEvent("fetch", resp.ok ? "info" : resp.status >= 500 ? "error" : "warn", data, requestId);
      return resp;
    } catch (e) {
      pushClientEvent("fetch.failed", "error", { method: init?.method ?? "GET", path: url.split("?")[0], ms: Math.round(performance.now() - started) });
      throw e;
    }
  };
}

export type AnyEvent = { seq: number; src: string; level: string; event: string; requestId?: string; data?: Record<string, unknown>; ts?: number };

export type Filter = "all" | "client" | "server" | "external" | "errors";

export function filterEvents(events: AnyEvent[], filter: Filter, highlightId?: string): AnyEvent[] {
  let out = events;
  if (filter === "client") out = out.filter((e) => e.src === "client");
  else if (filter === "server") out = out.filter((e) => e.src !== "client" && e.src !== "external");
  else if (filter === "external") out = out.filter((e) => e.src === "external");
  else if (filter === "errors") out = out.filter((e) => e.level === "error" || e.level === "warn");
  if (highlightId) out = out.filter((e) => e.requestId === highlightId);
  return out;
}

export function shouldToggleOnBacktick(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return true;
  const tag = target.tagName.toLowerCase();
  return tag !== "input" && tag !== "textarea" && !target.isContentEditable;
}
