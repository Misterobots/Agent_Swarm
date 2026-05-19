"use client";

import { useEffect } from "react";
import { useBuddyStore } from "@/lib/stores/buddy-store";
import { BuddySprite } from "./buddy-sprite";
import { X } from "lucide-react";

/**
 * Inline chat-thread buddy comment.
 * Renders as a small aside between message bubbles.
 * Injects when pendingComment is set in the store.
 * Auto-dismisses after 20 seconds; can also be manually closed.
 */
export function BuddyComment() {
  const { pendingComment, dismissComment, name, species, evolutionStage, mood } =
    useBuddyStore();

  const AUTO_DISMISS_MS = 20_000;

  useEffect(() => {
    if (!pendingComment) return;
    const id = setTimeout(dismissComment, AUTO_DISMISS_MS);
    return () => clearTimeout(id);
  }, [pendingComment, dismissComment]);

  if (!pendingComment) return null;

  return (
    <div className="flex items-start gap-2 px-4 py-2 mx-auto max-w-3xl animate-in slide-in-from-left-2 fade-in duration-300">
      {/* Sprite avatar */}
      <div className="flex-shrink-0 mt-0.5">
        <BuddySprite species={species} stage={evolutionStage} mood={mood} size={28} />
      </div>

      {/* Comment bubble */}
      <div className="relative flex-1 min-w-0 rounded-lg border border-[color:color-mix(in_srgb,var(--chat-accent)_30%,var(--chat-border))] bg-[color:color-mix(in_srgb,var(--chat-accent)_7%,var(--chat-panel))] px-3 py-2 text-[11px] text-[var(--chat-text)]">
        {/* Bubble tail */}
        <span className="absolute -left-[5px] top-3 w-2 h-2 rotate-45 border-l border-b border-[color:color-mix(in_srgb,var(--chat-accent)_30%,var(--chat-border))] bg-[color:color-mix(in_srgb,var(--chat-accent)_7%,var(--chat-panel))]" />

        <span className="font-semibold text-[var(--chat-accent)]">{name}: </span>
        <span className="italic">{pendingComment}</span>

        <button
          onClick={dismissComment}
          className="absolute top-1 right-1 p-0.5 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
          title="Dismiss"
        >
          <X size={9} />
        </button>
      </div>
    </div>
  );
}
