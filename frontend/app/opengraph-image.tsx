import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "findMe: find yourself in a photo album";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "#0A051B",
          color: "#F2F1F7",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <div
            style={{
              width: 0,
              height: 0,
              borderLeft: "38px solid transparent",
              borderRight: "38px solid transparent",
              borderBottom: "64px solid #5D29F0",
            }}
          />
          <div style={{ fontSize: 96, fontWeight: 600 }}>findMe</div>
        </div>
        <div style={{ fontSize: 40, marginTop: 28, color: "#A79FC2" }}>
          Find yourself in a photo album.
        </div>
        <div style={{ fontSize: 26, marginTop: 56, color: "#6E668A", fontFamily: "monospace" }}>
          face search on Runpod serverless · place + weather + camera enrichment · VLM captions
        </div>
      </div>
    ),
    size,
  );
}
