import { BACKEND_URL } from "@/lib/proxy";
import { diffToEvents, encodeEvent, terminal, type ProgressSnapshot } from "@/lib/sse";

const POLL_MS = 1000;
const MAX_LIFETIME_MS = 240_000;

export async function GET(req: Request, ctx: { params: Promise<{ albumId: string }> }) {
  const { albumId } = await ctx.params;
  let seq = Number(req.headers.get("last-event-id") ?? 0) || 0;

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      let prev: ProgressSnapshot | null = null;
      const started = Date.now();
      let alive = true;
      req.signal.addEventListener("abort", () => {
        alive = false;
      });
      while (alive && Date.now() - started < MAX_LIFETIME_MS) {
        let cur: ProgressSnapshot | null = null;
        try {
          const r = await fetch(`${BACKEND_URL()}/albums/${albumId}/status`, { cache: "no-store" });
          if (r.status === 404) {
            controller.enqueue(encoder.encode(`event: failed\ndata: {"stage":"failed"}\n\n`));
            break;
          }
          if (r.ok) cur = (await r.json()) as ProgressSnapshot;
        } catch {
          cur = null;
        }
        if (cur) {
          for (const e of diffToEvents(prev, cur, seq + 1)) {
            seq = e.id;
            controller.enqueue(encoder.encode(encodeEvent(e)));
          }
          if (terminal(cur)) break;
          prev = cur;
        }
        await new Promise((res) => setTimeout(res, POLL_MS));
      }
      try {
        controller.close();
      } catch {}
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
