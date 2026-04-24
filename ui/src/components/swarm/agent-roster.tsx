"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";
import { PioneerPortrait } from "./pioneer-portrait";

interface AgentRosterProps {
  workers: SwarmWorker[];
}

export function AgentRoster({ workers }: AgentRosterProps) {
  const [visible, setVisible] = useState<Set<string>>(new Set());

  // Stagger avatar reveal
  useEffect(() => {
    workers.forEach((w, i) => {
      setTimeout(() => setVisible((s) => new Set([...s, w.worker_id])), i * 120);
    });
  }, [workers]);

  // Pad to at least 6 ghost slots for visual consistency
  const slots = workers.length >= 6 ? workers : [
    ...workers,
    ...Array.from({ length: 6 - workers.length }, (_, i) => ({
      worker_id: `ghost-${i}`, role: "", pioneer_name: "···", pioneer_motto: "",
      task: "", phase: "", state: "pending" as const,
    })),
  ];

  return (
    <div className="flex flex-col items-center justify-center gap-4 w-full h-full px-6">
      <div className="grid grid-cols-3 gap-3 w-full max-w-xs">
        {slots.map((w) => {
          const isGhost = w.worker_id.startsWith("ghost-");
          const shown = visible.has(w.worker_id);
          return (
            <div
              key={w.worker_id}
              className={cn(
                "flex flex-col items-center gap-1.5 px-2 py-2 rounded-xl transition-all duration-300",
                isGhost ? "opacity-0" : shown ? "opacity-100 translate-y-0" : "opacity-0 translate-y-3",
                !isGhost && w.state === "running" && "ring-1 ring-[var(--chat-accent)]/50",
                !isGhost && "bg-white/5",
              )}
            >
              <div className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold border transition-all overflow-hidden",
                w.state === "completed" ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300" :
                w.state === "running" ? "bg-[var(--chat-accent)]/20 border-[var(--chat-accent)]/40 text-[var(--chat-accent)]" :
                w.state === "failed" ? "bg-red-500/20 border-red-500/40 text-red-300" :
                "bg-white/10 border-white/20 text-white/60",
              )}>
                {!isGhost && <PioneerPortrait role={w.role ?? ""} />}
              </div>
              {!isGhost && (
                <>
                  <p className="text-[10px] font-semibold text-white/80 text-center leading-none">{w.pioneer_name}</p>
                  <p className="text-[9px] text-white/40 capitalize">{w.role}</p>
                </>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-white/40 animate-pulse">Assembling swarm&hellip;</p>
    </div>
  );
}
