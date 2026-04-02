"use client";

interface ChatStatusBarProps {
  model: string;
  tokenPct: number;
  isStreaming: boolean;
  latestThought: string | null;
}

export function ChatStatusBar({ model, tokenPct, isStreaming, latestThought }: ChatStatusBarProps) {
  return (
    <div className="border-t border-[#2e2a27] bg-[#0f0f0f] px-4 py-2 text-xs text-zinc-400 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-[#cc785c]">MODEL</span>
        <span className="text-zinc-300">{model}</span>
        <span className="text-[#cc785c]">CTX</span>
        <span className={tokenPct >= 95 ? "text-red-400" : tokenPct >= 85 ? "text-orange-300" : "text-zinc-300"}>
          {tokenPct.toFixed(0)}%
        </span>
      </div>
      <div className="truncate max-w-[45%] text-right">
        {isStreaming ? latestThought || "Thinking..." : "Ready"}
      </div>
    </div>
  );
}
