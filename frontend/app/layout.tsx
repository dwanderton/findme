import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "findMe",
  description: "Find yourself in a photo album.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
