"use client";

import { Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function WorkshopToggle() {
  const workshopMode = useSettingsStore((s) => s.workshopMode);
  const setWorkshopMode = useSettingsStore((s) => s.setWorkshopMode);

  return (
    <button
      type="button"
      onClick={() => setWorkshopMode(!workshopMode)}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        workshopMode
          ? "bg-[color:color-mix(in_srgb,#f59e0b_18%,transparent)] text-amber-400 border-[color:color-mix(in_srgb,#f59e0b_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title="Workshop Mode — structured discovery interview (Grill Me)"
    >
      <Lightbulb size={14} />
      Workshop
    </button>
  );
}
