"use client";

import { Palette } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function DesignModeToggle() {
  const designMode = useSettingsStore((s) => s.designMode);
  const setDesignMode = useSettingsStore((s) => s.setDesignMode);

  return (
    <button
      type="button"
      onClick={() => setDesignMode(!designMode)}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        designMode
          ? "bg-[color:color-mix(in_srgb,#a855f7_18%,transparent)] text-purple-400 border-[color:color-mix(in_srgb,#a855f7_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title="Route through Open Design Studio"
    >
      <Palette size={14} />
      Design
    </button>
  );
}
