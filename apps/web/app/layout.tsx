import "./globals.css";
import "leaflet/dist/leaflet.css";
import type { Metadata } from "next";
import React from "react";

import { AppHeader } from "./components/app-header";
import { CompareTray } from "./components/compare-tray";

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
      <body>
        <AppHeader />
        {children}
        <CompareTray />
      </body>
    </html>
  );
}
