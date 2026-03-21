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
          ? "text-cyan-400 border-b-2 border-cyan-400"
          : "text-zinc-500 hover:text-zinc-300"
      )}
    >
      <Icon size={14} />
      {tool.label}
    </button>
  );
}
