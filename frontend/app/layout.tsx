import type { Metadata } from "next";
import "./globals.css";

const baseUrl = process.env.VERCEL_URL
  ? `https://${process.env.VERCEL_URL}`
  : "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: {
    default: "findMe",
    template: "%s · findMe",
  },
  description:
    "Find yourself in seconds. Face search on Runpod serverless GPUs; every match enriched with place, weather, camera settings, and a generated caption.",
  openGraph: {
    title: "findMe",
    description: "Find yourself in seconds.",
    siteName: "findMe",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "findMe",
    description: "Find yourself in seconds.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
