"use client";

import { Telescope } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function ResearchToggle() {
  const researchMode = useSettingsStore((s) => s.researchMode);
  const setResearchMode = useSettingsStore((s) => s.setResearchMode);

  return (
    <button
      type="button"
      onClick={() => setResearchMode(!researchMode)}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        researchMode
          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title="Toggle deep research mode (multi-step reasoning)"
    >
      <Telescope size={14} />
      Research
    </button>
  );
}
