"use client";

import { cn } from "@/lib/utils/cn";
import { ModelSelector } from "./model-selector";

interface ChatStatusBarProps {
  tokenPct: number;
  isStreaming: boolean;
  latestThought: string | null;
}

export function ChatStatusBar({ tokenPct, isStreaming, latestThought }: ChatStatusBarProps) {
  const ctxClass =
    tokenPct >= 95
      ? "text-red-400"
      : tokenPct >= 85
        ? "text-orange-300"
        : "text-[var(--chat-text)]";

  return (
    <div className="hidden md:flex border-t border-[var(--chat-border)] bg-[var(--chat-surface)] px-4 py-1.5 text-[11px] items-center justify-between gap-3">
      <div className="flex items-center gap-3 min-w-0">
        <StatusField label="Model" value={<ModelSelector compact />} />
        <span className="h-3 w-px bg-[var(--chat-border)]" />
        <StatusField
          label="Ctx"
          value={
            <span className={cn("font-medium tabular-nums", ctxClass)}>{tokenPct.toFixed(0)}%</span>
          }
        />
        <span className="h-3 w-px bg-[var(--chat-border)]" />
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full flex-shrink-0",
              isStreaming ? "bg-[var(--chat-accent)] animate-pulse" : "bg-emerald-400"
            )}
          />
          <span className="text-[var(--chat-muted)]">{isStreaming ? "Thinking" : "Ready"}</span>
        </div>
      </div>
      <div className="truncate max-w-[55%] text-right text-[var(--chat-subtle)] italic">
        {isStreaming ? latestThought || "" : ""}
      </div>
    </div>
  );
}

function StatusField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">
        {label}
      </span>
      {value}
    </div>
  );
}
