// ui/src/lib/hooks/use-goals.ts
"use client";

import { useEffect, useRef } from "react";
import { useGoalsStore } from "@/lib/stores/goals-store";
import { useChatStore } from "@/lib/stores/chat-store";

/**
 * Auto-goal hook — call this inside ChatView.
 *
 * Behaviour (mirrors Cowork's auto-task creation):
 *  - When a new user message is sent in a conversation, ensure an active goal
 *    exists for that thread.
 *  - Uses the first user message as the objective (truncated to 220 chars).
 *  - Only fires once per conversation — subsequent messages update usage, not goal.
 */
export function useAutoGoal() {
  const { activeConversationId, activeConversation } = useChatStore();
  const { activeGoal, ensureGoal, updateUsage } = useGoalsStore();
  const lastConvId = useRef<string | null>(null);
  const lastMessageCount = useRef<number>(0);

  useEffect(() => {
    const conv = activeConversation();
    if (!conv || !activeConversationId) return;

    const userMessages = conv.messages.filter((m) => m.role === "user");
    const msgCount = userMessages.length;

    // New conversation or first message sent
    if (activeConversationId !== lastConvId.current) {
      lastConvId.current = activeConversationId;
      lastMessageCount.current = msgCount;

      if (msgCount > 0) {
        const firstMsg = userMessages[0];
        const objective =
          typeof firstMsg.content === "string"
            ? firstMsg.content
            : conv.title ?? "New session";
        ensureGoal(activeConversationId, objective).catch(() => {
          // non-fatal — Goals backend may not be running locally
        });
      }
      return;
    }

    // Same conversation, new messages arrived — update usage estimate
    if (msgCount > lastMessageCount.current && activeGoal) {
      const delta = msgCount - lastMessageCount.current;
      lastMessageCount.current = msgCount;
      // Rough token estimate: 50 tokens per exchange
      updateUsage(activeGoal.id, delta * 50, 0).catch(() => {});
    }
  }, [activeConversationId, activeConversation, activeGoal, ensureGoal, updateUsage]);
}
