"use client";

import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";

const ROLE_INITIALS: Record<string, string> = {
  researcher: "SH", architect: "BA", coder: "KN",
  devops: "CE", analyst: "CO", verifier: "HO",
};

function initials(w: SwarmWorker) {
  return ROLE_INITIALS[w.role?.toLowerCase() ?? ""] ?? w.pioneer_name?.slice(0, 2).toUpperCase() ?? "??";
}

interface SwarmTaskCardsProps {
  workers: SwarmWorker[];
}

export function SwarmTaskCards({ workers }: SwarmTaskCardsProps) {
  if (workers.length === 0) return null;

  return (
    <div className="my-2 rounded-xl overflow-hidden border border-white/10 bg-white/5 text-sm">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-white/5 border-b border-white/10">
        <span className="text-base">🤖</span>
        <span className="font-semibold text-white/80">
          Agent Swarm &middot; {workers.length} Task{workers.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Task rows */}
      <div className="divide-y divide-white/5">
        {workers.map((w, i) => (
          <div
            key={w.worker_id}
            className={cn(
              "group relative flex items-center gap-3 px-3 py-2 transition-colors hover:bg-white/5 cursor-default",
            )}
          >
            {/* Avatar */}
            <div className={cn(
              "w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold border flex-shrink-0",
              w.state === "completed" ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300" :
              w.state === "running" ? "bg-[var(--chat-accent)]/20 border-[var(--chat-accent)]/40 text-[var(--chat-accent)]" :
              w.state === "failed" ? "bg-red-500/20 border-red-500/40 text-red-300" :
              "bg-white/10 border-white/20 text-white/60",
            )}>
              {initials(w)}
            </div>

            {/* Name + task */}
            <div className="flex-1 min-w-0">
              <span className="text-[11px] font-semibold text-white/70 mr-2">{w.pioneer_name}</span>
              <span className="text-[11px] text-white/40 truncate">{w.task?.slice(0, 60)}{(w.task?.length ?? 0) > 60 ? "…" : ""}</span>
            </div>

            {/* Index */}
            <span className="text-[10px] text-white/30 flex-shrink-0">{String(i + 1).padStart(2, "0")}</span>

            {/* Hover tooltip */}
            <div className="absolute left-12 bottom-full mb-1.5 z-50 hidden group-hover:block w-64 rounded-xl bg-gray-900 border border-white/15 shadow-xl px-3 py-2.5 pointer-events-none">
              <p className="text-[11px] font-bold text-white/90 mb-1">{w.pioneer_full_name ?? w.pioneer_name} &mdash; {w.role}</p>
              {w.pioneer_motto && (
                <p className="text-[10px] italic text-white/50 mb-1.5">&ldquo;{w.pioneer_motto}&rdquo;</p>
              )}
              <p className="text-[11px] text-white/70 leading-relaxed">{w.task}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
