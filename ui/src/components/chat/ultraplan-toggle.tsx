"use client";

import { Lock, Map, Link } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useFeaturePermissions } from "@/lib/hooks/use-feature-permissions";

export function UltraplanToggle() {
  const ultraplanMode = useSettingsStore((s) => s.ultraplanMode);
  const setUltraplanMode = useSettingsStore((s) => s.setUltraplanMode);
  const autoFeedPlan = useSettingsStore((s) => s.autoFeedPlan);
  const setAutoFeedPlan = useSettingsStore((s) => s.setAutoFeedPlan);
  const { isAllowed } = useFeaturePermissions();
  const permitted = isAllowed("planning");

  return (
    <div className="inline-flex items-center gap-0.5">
      <button
        type="button"
        onClick={() => permitted && setUltraplanMode(!ultraplanMode)}
        disabled={!permitted}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors disabled:cursor-not-allowed disabled:opacity-60",
          ultraplanMode
            ? "bg-[color:color-mix(in_srgb,var(--chat-accent-2)_18%,transparent)] text-[var(--chat-accent-2)] border-[color:color-mix(in_srgb,var(--chat-accent-2)_40%,var(--chat-border))]"
            : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
        )}
        title={permitted ? "UltraPlan: plan-only mode — decomposes task without execution" : "Planning access is disabled by your administrator"}
      >
        {permitted ? <Map size={14} /> : <Lock size={14} />}
        {permitted ? "Plan" : "Plan (Locked)"}
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
