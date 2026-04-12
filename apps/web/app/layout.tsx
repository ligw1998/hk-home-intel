import "./globals.css";
import "leaflet/dist/leaflet.css";
import type { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "HK Home Intel",
  description: "Local-first Hong Kong residential property research terminal",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
