"use client";

/**
 * Cross-device conversation sync.
 *
 * On mount: fetches conversations from the backend (scoped to the authenticated
 * user via x-authentik-username) and replaces the local Zustand store so the
 * same history is visible on every device.
 *
 * On delete: sends a DELETE to the backend before removing from local state.
 */

import { useEffect, useCallback } from "react";
import { useChatStore } from "@/lib/stores/chat-store";

const API = "/api/backend/v1/conversations";

export function useConversationSync() {
  const replaceConversations = useChatStore((s) => s.replaceConversations);
  const deleteConversationLocal = useChatStore((s) => s.deleteConversation);

  // Load from server once on mount — server is source of truth
  useEffect(() => {
    fetch(API)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { conversations?: unknown[] } | null) => {
        if (data?.conversations && data.conversations.length > 0) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          replaceConversations(data.conversations as any[]);
        }
      })
      .catch(() => {
        // Network unavailable — keep local store as-is
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Delete a conversation from both the server and the local store.
   * Call this instead of useChatStore deleteConversation directly.
   */
  const deleteConversation = useCallback(
    (convId: string) => {
      // Fire-and-forget server delete
      fetch(`${API}/${convId}`, { method: "DELETE" }).catch(() => {});
      // Remove from local state (switches active if needed)
      deleteConversationLocal(convId);
    },
    [deleteConversationLocal]
  );

  return { deleteConversation };
}
