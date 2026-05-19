"use client";

import { Map, Link } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function UltraplanToggle() {
  const ultraplanMode = useSettingsStore((s) => s.ultraplanMode);
  const setUltraplanMode = useSettingsStore((s) => s.setUltraplanMode);
  const autoFeedPlan = useSettingsStore((s) => s.autoFeedPlan);
  const setAutoFeedPlan = useSettingsStore((s) => s.setAutoFeedPlan);

  return (
    <div className="inline-flex items-center gap-0.5">
      <button
        type="button"
        onClick={() => setUltraplanMode(!ultraplanMode)}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
          ultraplanMode
            ? "bg-[color:color-mix(in_srgb,var(--chat-accent-2)_18%,transparent)] text-[var(--chat-accent-2)] border-[color:color-mix(in_srgb,var(--chat-accent-2)_40%,var(--chat-border))]"
            : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
        )}
        title="UltraPlan: plan-only mode — decomposes task without execution"
      >
        <Map size={14} />
        Plan
      </button>
      {ultraplanMode && (
        <button
          type="button"
          onClick={() => setAutoFeedPlan(!autoFeedPlan)}
          className={cn(
            "inline-flex items-center gap-1 px-1.5 py-1.5 rounded-md text-xs border transition-colors",
            autoFeedPlan
              ? "bg-[color:color-mix(in_srgb,var(--chat-accent-2)_18%,transparent)] text-[var(--chat-accent-2)] border-[color:color-mix(in_srgb,var(--chat-accent-2)_40%,var(--chat-border))]"
              : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
          )}
          title={autoFeedPlan ? "Auto-feed ON: plan will be injected as context for next message" : "Auto-feed OFF: you must explicitly request plan execution"}
        >
          <Link size={12} />
        </button>
      )}
    </div>
  );
}
