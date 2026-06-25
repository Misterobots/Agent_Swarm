"use client";

/**
 * ClientShell — root client boundary.
 *
 * Runs session resume BEFORE AppShell mounts so the UI never flashes
 * an empty state. On first load (or after a user switch) we fetch
 * conversations from the server and hydrate the Zustand store, then
 * render children. Subsequent renders skip the network call.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { ServiceWorkerRegistration } from "./sw-register";
import { useChatStore } from "@/lib/stores/chat-store";

const AppShell = dynamic(
  () => import("@/components/layout/app-shell").then((m) => m.AppShell),
  { ssr: false }
);

const API            = "/api/backend/v1/conversations";
const IDENTITY_KEY   = "memex-identity";
const USER_SCOPED    = ["memex-chats", "memex-buddy", "memex-dev", "memex-monitor", "memex-onboarding"];

async function resumeSession(replaceConversations: (c: unknown[]) => void): Promise<void> {
  // Identify current user
  let currentUser: string | null = null;
  try {
    const r = await fetch("/api/auth/me");
    if (r.ok) currentUser = (await r.json()).username ?? null;
  } catch {}

  // Clear stale state on user switch
  if (currentUser) {
    const stored = localStorage.getItem(IDENTITY_KEY);
    if (stored && stored !== currentUser) {
      USER_SCOPED.forEach((k) => { try { localStorage.removeItem(k); } catch {} });
      replaceConversations([]);
    }
    try { localStorage.setItem(IDENTITY_KEY, currentUser); } catch {}
  }

  // Load conversations (newest-first from server — replaceConversations auto-selects [0])
  try {
    const r = await fetch(API);
    if (!r.ok) return;
    const data = await r.json();
    if (Array.isArray(data?.conversations) && data.conversations.length > 0) {
      replaceConversations(data.conversations);
    }
  } catch {}
}

export function ClientShell({ children }: { children: React.ReactNode }) {
  const replaceConversations = useChatStore((s) => s.replaceConversations);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    resumeSession(replaceConversations).finally(() => setReady(true));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <ServiceWorkerRegistration />
      {!ready ? (
        <div className="flex h-screen items-center justify-center bg-[var(--chat-bg,#0e1117)]">
          <div className="flex flex-col items-center gap-3">
            <span className="text-[var(--chat-accent,#d97757)] text-2xl animate-pulse">◈</span>
            <span className="text-[var(--chat-muted,#6b7280)] text-xs">Resuming session…</span>
          </div>
        </div>
      ) : (
        <AppShell>{children}</AppShell>
      )}
    </>
  );
}
