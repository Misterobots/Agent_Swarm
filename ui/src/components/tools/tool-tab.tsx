"use client";

import { cn } from "@/lib/utils/cn";
import type { ToolDefinition } from "@/types/tools";

interface ToolTabProps {
  tool: ToolDefinition;
  active: boolean;
  onClick: () => void;
}

export function ToolTab({ tool, active, onClick }: ToolTabProps) {
  const Icon = tool.icon;

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap",
        active
          ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)]"
          : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
      )}
    >
      <Icon size={14} />
      {tool.label}
    </button>
  );
}
