"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";
import { PioneerPortrait } from "./pioneer-portrait";

// Status labels that cycle per worker
const STATUS_CYCLE = [
  "Analyzing", "Reasoning", "Researching", "Connecting",
  "Evaluating", "Designing", "Writing", "Verifying",
  "Identifying", "Acquiring", "Optimizing", "Integrating",
];

interface AgentDockProps {
  workers: SwarmWorker[];
  onSelect?: (id: string) => void;
}

export function AgentDock({ workers, onSelect }: AgentDockProps) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1800);
    return () => clearInterval(id);
  }, []);

  // Show up to 3 active workers; pad with placeholders
  const active = workers.filter((w) => w.state === "running" || w.state === "pending");
  const display = active.slice(0, 3);

  if (display.length === 0) return null;

  return (
    <div className="flex items-center justify-center gap-4 w-full py-4 px-3 flex-wrap">
      {display.map((w, i) => {
        const isRunning = w.state === "running";
        const statusIdx = (tick + i * 3) % STATUS_CYCLE.length;
        const status = isRunning ? STATUS_CYCLE[statusIdx] : "Queued";

        return (
          <div
            key={w.worker_id}
            onClick={() => onSelect?.(w.worker_id)}
            className={cn(
              "flex flex-col items-center gap-2 px-5 py-4 rounded-2xl transition-all min-w-[6rem]",
              "bg-white/5 border",
              onSelect && "cursor-pointer hover:bg-white/8",
              isRunning
                ? "border-[var(--chat-accent)]/35 shadow-[0_0_20px_var(--chat-accent)]/10"
                : "border-white/10",
            )}
          >
            <div className={cn(
              "relative w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold border overflow-hidden",
              isRunning
                ? "bg-[var(--chat-accent)]/20 border-[var(--chat-accent)]/50 text-[var(--chat-accent)]"
                : "bg-white/5 border-white/20 text-white/50",
            )}>
              <PioneerPortrait role={w.role ?? ""} />
              {isRunning && (
                <span className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-400 border-2 border-[var(--chat-bg)] animate-pulse" />
              )}
            </div>
            <p className="text-[11px] font-semibold text-white/75 text-center leading-none">{w.pioneer_name}</p>
            <p className="text-[9px] text-white/35 capitalize tracking-wide">{w.role}</p>
            <p
              key={status}
              className={cn(
                "text-[9px] font-bold tracking-wider transition-all duration-300 uppercase",
                isRunning ? "text-[var(--chat-accent)]" : "text-white/25",
              )}
            >
              {status}
            </p>
          </div>
        );
      })}
    </div>
  );
}
