"use client";

export const MAX_TILES = 60;

/* Demo album shown until the visitor uploads their own photos. */
export const DEFAULT_TILES = [
  "abby", "baby-bear", "bert", "big-bird", "cookie-monster", "cookie-monster-1",
  "cookie-monster-2", "count-von-count", "elmo", "ernie", "gabrielle", "gonger",
  "grover", "ji-young", "julia", "oscar", "rosita", "rudy", "snuffy", "tamir",
  "tango", "telly", "zoe",
].map((name) => `/muppets/${name}.avif`);

export function pickTiles(uploadUrls: string[], servedUrls: string[]): string[] {
  const source = servedUrls.length > 0 ? servedUrls : uploadUrls;
  if (source.length <= MAX_TILES) return source;
  const step = source.length / MAX_TILES;
  return Array.from({ length: MAX_TILES }, (_, i) => source[Math.floor(i * step)]);
}

export function columnize(tiles: string[], columns = 4): string[][] {
  return Array.from({ length: columns }, (_, c) => tiles.filter((_, i) => i % columns === c));
}

export function Backdrop({
  uploadUrls,
  servedUrls,
  dimmed = false,
}: {
  uploadUrls: string[];
  servedUrls: string[];
  dimmed?: boolean;
}) {
  const picked = pickTiles(uploadUrls, servedUrls);
  const tiles = picked.length > 0 ? picked : DEFAULT_TILES;
  const cols = columnize(tiles).filter((c) => c.length > 0);

  return (
    <>
      <div aria-hidden data-testid="backdrop" className={`marquee ${dimmed ? "dimmed" : ""}`}>
        {cols.map((col, ci) => (
          <div className="mq-col" key={ci}>
            {[...col, ...col, ...col, ...col].map((src, i) => (
              <img key={`${src}-${i}`} src={src} alt="" loading={i < 3 ? "eager" : "lazy"} decoding="async" />
            ))}
          </div>
        ))}
      </div>
      <div className="mq-veil" aria-hidden />
      <style>{`
        .marquee {
          position: fixed;
          inset: -12vh -6vw;
          z-index: 0;
          display: flex;
          gap: 1.2vw;
          transform: rotate(-3.5deg) scale(1.08);
          opacity: 0.85;
          transition: opacity 1.2s ease;
          overflow: hidden;
        }
        .marquee.dimmed { opacity: 0.38; }
        .mq-col {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 1.2vw;
          animation: mq-up 90s linear infinite;
          will-change: transform;
          transform: translate3d(0, 0, 0);
        }
        .mq-col:nth-child(2) { animation-duration: 120s; animation-direction: reverse; }
        .mq-col:nth-child(3) { animation-duration: 100s; }
        .mq-col:nth-child(4) { animation-duration: 140s; animation-direction: reverse; }
        @keyframes mq-up {
          from { transform: translate3d(0, 0, 0); }
          to { transform: translate3d(0, -50%, 0); }
        }
        .mq-col img {
          width: 100%;
          aspect-ratio: 3 / 2;
          object-fit: cover;
          border-radius: 4px;
          filter: grayscale(0.3) contrast(0.95) brightness(0.8);
        }
        .mq-veil {
          position: fixed;
          inset: 0;
          z-index: 1;
          pointer-events: none;
          background:
            radial-gradient(ellipse 80% 60% at 50% 38%, oklch(0.13 0.05 291 / 0.42) 0%, oklch(0.13 0.05 291 / 0.82) 75%),
            linear-gradient(180deg, oklch(0.13 0.05 291 / 0.55), oklch(0.13 0.05 291 / 0.22) 30%, oklch(0.13 0.05 291 / 0.8) 100%);
        }
        @media (prefers-reduced-motion: reduce) {
          .mq-col { animation: none; }
        }
      `}</style>
    </>
  );
}
