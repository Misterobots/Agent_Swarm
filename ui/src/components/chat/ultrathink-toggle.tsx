"use client";

import { BrainCircuit } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function UltrathinkToggle() {
  const ultrathinkMode = useSettingsStore((s) => s.ultrathinkMode);
  const setUltrathinkMode = useSettingsStore((s) => s.setUltrathinkMode);

  return (
    <button
      type="button"
      onClick={() => setUltrathinkMode(!ultrathinkMode)}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        ultrathinkMode
          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title="UltraThink: extended reasoning depth for complex problems"
    >
      <BrainCircuit size={14} />
      Think
    </button>
  );
}
