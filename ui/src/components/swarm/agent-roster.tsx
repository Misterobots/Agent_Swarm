"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";
import { PioneerPortrait } from "./pioneer-portrait";

const ROLE_THEME: Record<string, { text: string; bg: string; border: string; stripe: string; accent: string }> = {
  researcher: { text: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/30",   stripe: "bg-amber-400",   accent: "#f59e0b" },
  architect:  { text: "text-blue-400",    bg: "bg-blue-500/10",    border: "border-blue-500/30",    stripe: "bg-blue-400",    accent: "#3b82f6" },
  coder:      { text: "text-violet-400",  bg: "bg-violet-500/10",  border: "border-violet-500/30",  stripe: "bg-violet-400",  accent: "#8b5cf6" },
  devops:     { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30", stripe: "bg-emerald-400", accent: "#10b981" },
  analyst:    { text: "text-cyan-400",    bg: "bg-cyan-500/10",    border: "border-cyan-500/30",    stripe: "bg-cyan-400",    accent: "#06b6d4" },
  verifier:   { text: "text-rose-400",    bg: "bg-rose-500/10",    border: "border-rose-500/30",    stripe: "bg-rose-400",    accent: "#f43f5e" },
};
const DEFAULT_THEME = { text: "text-[var(--chat-muted)]", bg: "bg-[var(--chat-soft)]", border: "border-[var(--chat-border)]", stripe: "bg-[var(--chat-muted)]", accent: "" };

interface AgentRosterProps {
  workers: SwarmWorker[];
}

export function AgentRoster({ workers }: AgentRosterProps) {
  const [visible, setVisible] = useState<Set<string>>(new Set());

  useEffect(() => {
    workers.forEach((w, i) => {
      setTimeout(() => setVisible((s) => new Set([...s, w.worker_id])), i * 120);
    });
  }, [workers]);

  const slots = workers.length >= 6 ? workers : [
    ...workers,
    ...Array.from({ length: 6 - workers.length }, (_, i) => ({
      worker_id: `ghost-${i}`, role: "", pioneer_name: "···", pioneer_motto: "",
      task: "", phase: "", state: "pending" as const,
    })),
  ];

  return (
    <div className="flex flex-col items-center justify-center gap-4 w-full h-full px-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 w-full max-w-sm">
        {slots.map((w) => {
          const isGhost = w.worker_id.startsWith("ghost-");
          const shown = visible.has(w.worker_id);
          const role = w.role?.toLowerCase() ?? "";
          const theme = ROLE_THEME[role] ?? DEFAULT_THEME;
          const stateColor =
            w.state === "completed" ? "bg-emerald-400" :
            w.state === "running"   ? "bg-[var(--chat-accent)] animate-pulse" :
            w.state === "failed"    ? "bg-red-400" : "bg-[var(--chat-muted)]";

          return (
            <div
              key={w.worker_id}
              className={cn(
                "flex flex-col rounded-lg overflow-hidden border transition-all duration-300",
                "bg-[var(--chat-panel)]",
                isGhost
                  ? "opacity-0 border-[var(--chat-border)]"
                  : shown
                  ? "opacity-100 translate-y-0 border-[var(--chat-border)]"
                  : "opacity-0 translate-y-3 border-[var(--chat-border)]",
                !isGhost && w.state === "running" && "ring-1 ring-[var(--chat-accent)]/40",
              )}
            >
              {/* Role accent top stripe */}
              {!isGhost && (
                <div className={cn("h-0.5 w-full flex-shrink-0", theme.stripe)} />
              )}

              {/* Portrait */}
              <div className="flex justify-center pt-2.5 pb-1">
                <div className={cn(
                  "w-10 h-10 rounded-full border overflow-hidden flex-shrink-0",
                  isGhost ? "bg-[var(--chat-soft)] border-[var(--chat-border)]" :
                  w.state === "completed" ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-400" :
                  w.state === "running"   ? "bg-[var(--chat-accent)]/15 border-[var(--chat-accent)]/40 text-[var(--chat-accent)]" :
                  w.state === "failed"    ? "bg-red-500/15 border-red-500/40 text-red-400" :
                  cn(theme.bg, theme.border, theme.text),
                )}>
                  {!isGhost && <PioneerPortrait role={role} />}
                </div>
              </div>

              {/* Name + role */}
              {!isGhost && (
                <div className="px-1.5 pb-2 text-center">
                  <p className="text-[10px] font-bold text-[var(--chat-text)] truncate leading-snug">{w.pioneer_name}</p>
                  <p className={cn("text-[8px] uppercase tracking-wider mt-0.5 font-semibold", theme.text)}>{w.role}</p>
                </div>
              )}

              {/* State dot at bottom */}
              {!isGhost && (
                <div className={cn("h-0.5 w-full flex-shrink-0 opacity-60", stateColor)} />
              )}
            </div>
          );
        })}
      </div>
      <p className="text-[11px] text-[var(--chat-muted)] animate-pulse">Assembling swarm&hellip;</p>
    </div>
  );
}
