"use client";

import dynamic from "next/dynamic";

const AppShell = dynamic(
  () => import("@/components/layout/app-shell").then((m) => m.AppShell),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-screen items-center justify-center bg-[#0e1117]">
        <div className="text-cyan-400 text-sm animate-pulse">Loading...</div>
      </div>
    ),
  }
);

export function ClientShell({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
