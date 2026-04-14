import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ClientShell } from "@/components/layout/client-shell";
import "./globals.css";
import "@xterm/xterm/css/xterm.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Hive Mind — AI Swarm Interface",
  description: "Unified interface for the Home AI Lab swarm",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ClientShell>{children}</ClientShell>
      </body>
    </html>
  );
}
