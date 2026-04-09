"use client";

interface ChatStatusBarProps {
  model: string;
  tokenPct: number;
  isStreaming: boolean;
  latestThought: string | null;
}

export function ChatStatusBar({ model, tokenPct, isStreaming, latestThought }: ChatStatusBarProps) {
  return (
    <div className="border-t border-[var(--chat-border)] bg-[var(--chat-surface)] px-4 py-2 text-xs text-[var(--chat-muted)] flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-[var(--chat-accent)]">MODEL</span>
        <span className="text-[var(--chat-text)]">{model}</span>
        <span className="text-[var(--chat-accent)]">CTX</span>
        <span className={tokenPct >= 95 ? "text-red-400" : tokenPct >= 85 ? "text-orange-300" : "text-[var(--chat-text)]"}>
          {tokenPct.toFixed(0)}%
        </span>
      </div>
      <div className="truncate max-w-[45%] text-right">
        {isStreaming ? latestThought || "Thinking..." : "Ready"}
      </div>
    </div>
  );
}
