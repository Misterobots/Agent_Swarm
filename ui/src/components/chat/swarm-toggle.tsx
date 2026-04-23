"use client";

import { Network } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function SwarmToggle() {
  const swarmMode = useSettingsStore((s) => s.swarmMode);
  const setSwarmMode = useSettingsStore((s) => s.setSwarmMode);

  return (
    <button
      type="button"
      onClick={() => setSwarmMode(!swarmMode)}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
        swarmMode
          ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
      )}
      title="Route through Lamport multi-agent coordinator (Swarm Mode)"
    >
      <Network size={14} />
      Swarm
    </button>
  );
}
