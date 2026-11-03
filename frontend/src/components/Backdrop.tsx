"use client";

export const MAX_TILES = 60;

export function pickTiles(uploadUrls: string[], servedUrls: string[]): string[] {
  const source = servedUrls.length > 0 ? servedUrls : uploadUrls;
  if (source.length <= MAX_TILES) return source;
  const step = source.length / MAX_TILES;
  return Array.from({ length: MAX_TILES }, (_, i) => source[Math.floor(i * step)]);
}

export function Backdrop({ uploadUrls, servedUrls }: { uploadUrls: string[]; servedUrls: string[] }) {
  const tiles = pickTiles(uploadUrls, servedUrls);
  if (!tiles.length) return null;
  return (
    <div
      aria-hidden
      data-testid="backdrop"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -1,
        overflow: "hidden",
      }}
    >
      <div
        className="backdrop-drift"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: 4,
          minHeight: "120vh",
          opacity: 0.38,
          filter: "saturate(0.85)",
        }}
      >
        {tiles.map((url, i) => (
          <img
            key={url}
            src={url}
            alt=""
            loading="lazy"
            className="log-stream"
            style={{
              width: "100%",
              aspectRatio: "1",
              objectFit: "cover",
              animationDelay: `${(i % 12) * 40}ms`,
            }}
          />
        ))}
      </div>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "linear-gradient(180deg, oklch(0.13 0.05 291 / 0.5), oklch(0.13 0.05 291 / 0.82))",
        }}
      />
      <style>{`
        .backdrop-drift { animation: backdrop-drift 60s linear infinite alternate; }
        @keyframes backdrop-drift {
          from { transform: translateY(0); }
          to { transform: translateY(-12vh); }
        }
        @media (prefers-reduced-motion: reduce) {
          .backdrop-drift { animation: none; }
        }
      `}</style>
    </div>
  );
}
