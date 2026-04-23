"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";

const ROLE_INITIALS: Record<string, string> = {
  researcher: "SH", architect: "BA", coder: "KN",
  devops: "CE", analyst: "CO", verifier: "HO",
};

// Status labels that cycle per worker
const STATUS_CYCLE = [
  "Analyzing", "Reasoning", "Researching", "Connecting",
  "Evaluating", "Designing", "Writing", "Verifying",
  "Identifying", "Acquiring", "Optimizing", "Integrating",
];

function initials(w: SwarmWorker) {
  return ROLE_INITIALS[w.role?.toLowerCase() ?? ""] ?? w.pioneer_name?.slice(0, 2).toUpperCase() ?? "??";
}

interface AgentDockProps {
  workers: SwarmWorker[];
}

export function AgentDock({ workers }: AgentDockProps) {
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
    <div className="flex items-center justify-center gap-3 w-full py-3">
      {display.map((w, i) => {
        const isRunning = w.state === "running";
        const statusIdx = (tick + i * 3) % STATUS_CYCLE.length;
        const status = isRunning ? STATUS_CYCLE[statusIdx] : "Queued";

        return (
          <div
            key={w.worker_id}
            className={cn(
              "flex flex-col items-center gap-1.5 px-3 py-2 rounded-xl transition-all",
              "bg-white/5 border",
              isRunning
                ? "border-[var(--chat-accent)]/30 shadow-[0_0_12px_var(--chat-accent)]/10"
                : "border-white/10",
            )}
          >
            <div className={cn(
              "relative w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold border",
              isRunning
                ? "bg-[var(--chat-accent)]/20 border-[var(--chat-accent)]/50 text-[var(--chat-accent)]"
                : "bg-white/5 border-white/20 text-white/50",
            )}>
              {initials(w)}
              {isRunning && (
                <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border border-[var(--chat-bg)] animate-pulse" />
              )}
            </div>
            <p className="text-[10px] text-white/60 font-medium">{String(i + 1).padStart(2, "0")}</p>
            <p
              key={status}
              className={cn(
                "text-[9px] font-semibold tracking-wide transition-all duration-300",
                isRunning ? "text-[var(--chat-accent)]" : "text-white/30",
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
