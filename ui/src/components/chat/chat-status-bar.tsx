"use client";

import { cn } from "@/lib/utils/cn";

interface ChatStatusBarProps {
  model: string;
  tokenPct: number;
  isStreaming: boolean;
  latestThought: string | null;
}

export function ChatStatusBar({ model, tokenPct, isStreaming, latestThought }: ChatStatusBarProps) {
  return (
    <div className="flex items-center justify-between px-4 py-1 border-t border-[var(--chat-border)] bg-[var(--chat-surface)] text-[10px] text-[var(--chat-muted)]">
      <span className="truncate max-w-[40%]">
        {isStreaming && latestThought
          ? latestThought
          : `Model: ${model}`}
      </span>
      <span
        className={cn(
          "tabular-nums",
          tokenPct >= 95 ? "text-red-400" : tokenPct >= 80 ? "text-amber-400" : ""
        )}
      >
        ctx {tokenPct.toFixed(0)}%
      </span>
    </div>
  );
}
