"use client";

interface ChatStatusBarProps {
  model: string;
  tokenPct: number;
  isStreaming: boolean;
  latestThought: string | null;
}

export function ChatStatusBar({ model, tokenPct, isStreaming, latestThought }: ChatStatusBarProps) {
  return (
    <div className="border-t border-[var(--chat-border)] bg-[var(--chat-surface)] px-4 py-2 text-xs flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 flex-shrink-0">
        {/* Live indicator */}
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${isStreaming ? "bg-[var(--chat-accent)] status-pulse" : "bg-[var(--chat-muted)] opacity-40"}`} />
        <span className="font-mono text-[var(--chat-accent)]">{model}</span>
        <span className="text-[var(--chat-border)]">|</span>
        <span className={`font-mono ${tokenPct >= 95 ? "text-red-400" : tokenPct >= 85 ? "text-orange-300" : "text-[var(--chat-muted)]"}`}>
          CTX {tokenPct.toFixed(0)}%
        </span>
      </div>
      <div className="flex-1 min-w-0 text-right">
        {isStreaming ? (
          <span className="text-[var(--chat-accent-strong)] truncate block streaming-caret">
            {latestThought || "Thinking..."}
          </span>
        ) : (
          <span className="text-[var(--chat-muted)]">Ready</span>
        )}
      </div>
    </div>
  );
}
