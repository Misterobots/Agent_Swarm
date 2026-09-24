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
import { usePathname } from "next/navigation";
import { ServiceWorkerRegistration } from "./sw-register";
import { useChatStore } from "@/lib/stores/chat-store";
import type { Conversation } from "@/types/chat";

// Routes with no app chrome at all — the public landing page and its
// children render full-bleed, with no sidebar and no session/conversation
// fetch (there's nothing to resume for an anonymous visitor).
const CHROMELESS_PREFIXES = ["/download"];
function isChromeless(pathname: string | null): boolean {
  if (!pathname) return false;
  return pathname === "/" || CHROMELESS_PREFIXES.some((p) => pathname.startsWith(p));
}

const AppShell = dynamic(
  () => import("@/components/layout/app-shell").then((m) => m.AppShell),
  { ssr: false }
);

const API            = "/api/backend/v1/conversations";
const IDENTITY_KEY   = "memex-identity";
const USER_SCOPED    = ["memex-chats", "memex-buddy", "memex-dev", "memex-monitor", "memex-onboarding"];

async function resumeSession(replaceConversations: (c: Conversation[]) => void): Promise<void> {
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
      replaceConversations(data.conversations as Conversation[]);
    }
  } catch {}
}

export function ClientShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const chromeless = isChromeless(pathname);
  const replaceConversations = useChatStore((s) => s.replaceConversations);
  const [ready, setReady] = useState(chromeless);

  useEffect(() => {
    if (chromeless) return;
    resumeSession(replaceConversations).finally(() => setReady(true));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chromeless]);

  if (chromeless) return <>{children}</>;

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
