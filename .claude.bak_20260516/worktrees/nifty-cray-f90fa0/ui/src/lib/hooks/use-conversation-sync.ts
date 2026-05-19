"use client";

/**
 * Cross-device conversation sync + user identity guard.
 *
 * On mount:
 *  1. Fetch the current authenticated user from /api/auth/me (reads Authentik headers).
 *  2. Compare against the last known user stored in localStorage.
 *  3. If the user has changed, clear all user-scoped localStorage keys so the
 *     incoming user never sees a previous user's state.
 *  4. Fetch conversations from the backend (scoped to the authenticated user via
 *     x-authentik-username) and replace the local Zustand store.
 *
 * On delete: sends a DELETE to the backend before removing from local state.
 */

import { useEffect, useCallback } from "react";
import { useChatStore } from "@/lib/stores/chat-store";

const API = "/api/backend/v1/conversations";
const IDENTITY_KEY = "memex-identity";

// All localStorage keys that contain per-user state and must be cleared on user switch.
const USER_SCOPED_KEYS = [
  "memex-chats",
  "memex-buddy",
  "memex-dev",
  "memex-monitor",
];

function clearUserScopedStorage() {
  for (const key of USER_SCOPED_KEYS) {
    try { localStorage.removeItem(key); } catch { /* SSR / private mode */ }
  }
}

function getStoredIdentity(): string | null {
  try { return localStorage.getItem(IDENTITY_KEY); } catch { return null; }
}

function setStoredIdentity(username: string) {
  try { localStorage.setItem(IDENTITY_KEY, username); } catch { /* best-effort */ }
}

export function useConversationSync() {
  const replaceConversations = useChatStore((s) => s.replaceConversations);
  const deleteConversationLocal = useChatStore((s) => s.deleteConversation);

  useEffect(() => {
    async function syncOnMount() {
      // Step 1: Identify the current authenticated user
      let currentUser: string | null = null;
      try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
          const data = await res.json();
          currentUser = data.username ?? null;
        }
      } catch {
        // Network unavailable — proceed with existing local state
      }

      // Step 2: Detect user switch — clear stale state before loading new user's data
      if (currentUser) {
        const storedUser = getStoredIdentity();
        if (storedUser && storedUser !== currentUser) {
          clearUserScopedStorage();
          replaceConversations([]);
        }
        setStoredIdentity(currentUser);
      }

      // Step 3: Load conversations from server (source of truth for cross-device sync)
      try {
        const r = await fetch(API);
        if (!r.ok) return;
        const data: { conversations?: unknown[] } = await r.json();
        if (data?.conversations && data.conversations.length > 0) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          replaceConversations(data.conversations as any[]);
        }
        // If server returns 0 conversations, keep local state — user may have
        // conversations not yet synced, and clearing would orphan activeConversationId.
      } catch {
        // Network unavailable — keep local store as-is
      }
    }

    void syncOnMount();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const deleteConversation = useCallback(
    (convId: string) => {
      fetch(`${API}/${convId}`, { method: "DELETE" }).catch(() => {});
      deleteConversationLocal(convId);
    },
    [deleteConversationLocal]
  );

  return { deleteConversation };
}
