"use client";

import dynamic from "next/dynamic";
import { ServiceWorkerRegistration } from "./sw-register";

const AppShell = dynamic(
  () => import("@/components/layout/app-shell").then((m) => m.AppShell),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-screen items-center justify-center bg-[var(--chat-bg)]">
        <div className="text-[var(--chat-accent)] text-sm animate-pulse">Loading...</div>
      </div>
    ),
  }
);

export function ClientShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ServiceWorkerRegistration />
      <AppShell>{children}</AppShell>
    </>
  );
}
