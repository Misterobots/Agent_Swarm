import type { Metadata, Viewport } from "next";
import { ClientShell } from "@/components/layout/client-shell";
import "./globals.css";
import "@xterm/xterm/css/xterm.css";

// Use system fonts to avoid next/font/google Turbopack issues
const geistSans = { variable: "--font-geist-sans", className: "" };
const geistMono = { variable: "--font-geist-mono", className: "" };

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#0e1117",
};

export const metadata: Metadata = {
  title: "Memex — AI Swarm Interface",
  description: "Unified interface for the Home AI Lab swarm",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Memex",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="memex" data-mode="dark" suppressHydrationWarning>
      <head>
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        {/* Landing page only — Space Grotesk (display) + IBM Plex Sans/Mono (body/labels).
            Plain <link>, not next/font/google — this app avoids that loader due to
            Turbopack issues (see geistSans/geistMono below). */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ClientShell>{children}</ClientShell>
      </body>
    </html>
  );
}
