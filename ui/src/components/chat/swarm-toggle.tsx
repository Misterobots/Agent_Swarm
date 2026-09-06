"use client";

import { Lock, Network } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useFeaturePermissions } from "@/lib/hooks/use-feature-permissions";

export function SwarmToggle() {
  const swarmMode = useSettingsStore((s) => s.swarmMode);
  const setSwarmMode = useSettingsStore((s) => s.setSwarmMode);
  const { isAllowed } = useFeaturePermissions();
  const permitted = isAllowed("swarm");

  return (
    <button
        type="button"
        onClick={() => permitted && setSwarmMode(!swarmMode)}
        disabled={!permitted}
      className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        swarmMode
          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
        title={permitted ? "Route through Lamport multi-agent coordinator (Swarm Mode)" : "Swarm access is disabled by your administrator"}
      >
        {permitted ? <Network size={14} /> : <Lock size={14} />}
        {permitted ? "Swarm" : "Swarm (Locked)"}
    </button>
  );
}
