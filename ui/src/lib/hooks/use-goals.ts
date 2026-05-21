// ui/src/lib/hooks/use-goals.ts
"use client";

import { useEffect, useRef } from "react";
import { useGoalsStore } from "@/lib/stores/goals-store";
import { useChatStore } from "@/lib/stores/chat-store";

/**
 * useAutoGoal — usage tracking for an explicitly-activated goal.
 *
 * Goals are deliberately enabled via the GoalsToggle in Chat Settings,
 * NOT auto-created on every message send. This hook only handles the
 * secondary concern: updating token-usage estimates as messages arrive
 * while Goals mode is already active.
 *
 * Goal creation lives in GoalsToggle → useGoalsStore.ensureGoal().
 */
export function useAutoGoal() {
  const { activeConversationId, activeConversation } = useChatStore();
  const { activeGoal, updateUsage } = useGoalsStore();
  const lastConvId = useRef<string | null>(null);
  const lastMessageCount = useRef<number>(0);

  useEffect(() => {
    const conv = activeConversation();
    if (!conv || !activeConversationId) return;

    const userMessages = conv.messages.filter((m) => m.role === "user");
    const msgCount = userMessages.length;

    // Reset counters when the conversation changes
    if (activeConversationId !== lastConvId.current) {
      lastConvId.current = activeConversationId;
      lastMessageCount.current = msgCount;
      return;
    }

    // If Goals is active and new messages arrived, update usage estimate
    if (msgCount > lastMessageCount.current && activeGoal) {
      const delta = msgCount - lastMessageCount.current;
      lastMessageCount.current = msgCount;
      // Rough token estimate: 50 tokens per exchange
      updateUsage(activeGoal.id, delta * 50, 0).catch(() => {});
    }
  }, [activeConversationId, activeConversation, activeGoal, updateUsage]);
}
