"use client";

import { Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function WorkshopToggle() {
  const workshopMode = useSettingsStore((s) => s.workshopMode);
  const setWorkshopMode = useSettingsStore((s) => s.setWorkshopMode);

  return (
    <div className="relative group/wt">
      <button
        type="button"
        onClick={() => setWorkshopMode(!workshopMode)}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
          workshopMode
            ? "bg-[color:color-mix(in_srgb,#f59e0b_18%,transparent)] text-amber-400 border-[color:color-mix(in_srgb,#f59e0b_40%,var(--chat-border))]"
            : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
        )}
      >
        <Lightbulb size={14} />
        Workshop
      </button>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover/wt:block z-50 w-56 px-2.5 py-2 rounded-md text-[10px] leading-snug bg-[var(--chat-panel)] border border-[var(--chat-border)] text-[var(--chat-muted)] shadow-lg pointer-events-none text-center whitespace-normal">
        Structured discovery: 7 idea-specific questions → Product Brief → Design &amp; Build prompts
      </div>
    </div>
  );
}
