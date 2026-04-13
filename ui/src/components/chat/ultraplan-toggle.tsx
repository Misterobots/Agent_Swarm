"use client";

import { Map } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function UltraplanToggle() {
  const ultraplanMode = useSettingsStore((s) => s.ultraplanMode);
  const setUltraplanMode = useSettingsStore((s) => s.setUltraplanMode);

  return (
    <button
      type="button"
      onClick={() => setUltraplanMode(!ultraplanMode)}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        ultraplanMode
          ? "bg-[color:color-mix(in_srgb,var(--chat-accent-2)_18%,transparent)] text-[var(--chat-accent-2)] border-[color:color-mix(in_srgb,var(--chat-accent-2)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title="UltraPlan: multi-step planning mode with detailed task breakdown"
    >
      <Map size={14} />
      Plan
    </button>
  );
}
