"use client";

import { Target } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useGoalsStore } from "@/lib/stores/goals-store";
import { useChatStore } from "@/lib/stores/chat-store";

/**
 * GoalsToggle — explicit per-thread Goals mode control.
 *
 * Sits in the Chat Settings modes grid. When enabled it calls ensureGoal
 * to create (or retrieve) the goal for the active thread and opens the
 * GoalsPanel. When disabled it clears the goal from the UI (does NOT
 * delete from the DB — the goal remains paused on the backend).
 */
export function GoalsToggle() {
  const activeGoal    = useGoalsStore((s) => s.activeGoal);
  const ensureGoal    = useGoalsStore((s) => s.ensureGoal);
  const clearGoal     = useGoalsStore((s) => s.clearGoal);
  const setPanelOpen  = useGoalsStore((s) => s.setPanelOpen);

  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const activeConversation   = useChatStore((s) => s.activeConversation);

  const goalsOn = !!activeGoal;

  const handleToggle = async () => {
    if (goalsOn) {
      clearGoal();
      return;
    }

    if (!activeConversationId) return;

    const conv = activeConversation();
    const firstUserMsg = conv?.messages?.find((m) => m.role === "user");
    const objective =
      typeof firstUserMsg?.content === "string"
        ? firstUserMsg.content.slice(0, 220)
        : conv?.title ?? "Goals session";

    try {
      await ensureGoal(activeConversationId, objective);
      setPanelOpen(true);
    } catch {
      // non-fatal — backend may be unavailable
    }
  };

  return (
    <button
      type="button"
      onClick={() => void handleToggle()}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        goalsOn
          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title="Track goals & plan steps for this conversation"
    >
      <Target size={14} />
      Goals
    </button>
  );
}
