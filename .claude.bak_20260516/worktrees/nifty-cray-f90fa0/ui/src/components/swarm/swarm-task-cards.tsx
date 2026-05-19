"use client";

import { cn } from "@/lib/utils/cn";
import type { SwarmWorker } from "@/types/chat";
import { PioneerPortrait } from "./pioneer-portrait";
import { useSwarmStore } from "@/lib/stores/swarm-store";

const ROLE_THEME: Record<string, { text: string; bg: string; border: string }> = {
  researcher: { text: "text-amber-400",   bg: "bg-amber-500/20",   border: "border-amber-500/40" },
  architect:  { text: "text-blue-400",    bg: "bg-blue-500/20",    border: "border-blue-500/40" },
  coder:      { text: "text-violet-400",  bg: "bg-violet-500/20",  border: "border-violet-500/40" },
  devops:     { text: "text-emerald-400", bg: "bg-emerald-500/20", border: "border-emerald-500/40" },
  analyst:    { text: "text-cyan-400",    bg: "bg-cyan-500/20",    border: "border-cyan-500/40" },
  verifier:   { text: "text-rose-400",    bg: "bg-rose-500/20",    border: "border-rose-500/40" },
};
const DEFAULT_THEME = {
  text:   "text-[var(--chat-muted)]",
  bg:     "bg-[var(--chat-soft)]",
  border: "border-[var(--chat-border)]",
};

interface SwarmTaskCardsProps {
  workers: SwarmWorker[];
}

export function SwarmTaskCards({ workers }: SwarmTaskCardsProps) {
  const { setSelectedWorker, setTheaterPhase, setActive } = useSwarmStore();

  if (workers.length === 0) return null;

  function handleRowClick(w: SwarmWorker) {
    setActive(true);
    setTheaterPhase("working");
    setSelectedWorker(w.worker_id);
  }

  return (
    <div className="my-2 rounded-lg overflow-hidden border border-[var(--chat-border)] bg-[var(--chat-surface)] text-sm">
      <div className="flex items-center gap-2 px-3 py-2 bg-[var(--chat-panel)] border-b border-[var(--chat-border)]">
        <span className="text-base">🤖</span>
        <span className="font-semibold text-[var(--chat-text)]">
          Agent Swarm &middot; {workers.length} Task{workers.length !== 1 ? "s" : ""}
        </span>
        <span className="ml-auto text-[9px] text-[var(--chat-muted)]">click to inspect</span>
      </div>

      <div className="divide-y divide-[var(--chat-border)]">
        {workers.map((w, i) => {
          const role = w.role?.toLowerCase() ?? "";
          const theme = ROLE_THEME[role] ?? DEFAULT_THEME;
          return (
            <button
              key={w.worker_id}
              onClick={() => handleRowClick(w)}
              className={cn(
                "group relative w-full flex items-center gap-3 px-3 py-2 text-left",
                "transition-colors hover:bg-[var(--hover-tint)] cursor-pointer",
              )}
            >
              <div className={cn(
                "w-7 h-7 rounded-full border flex-shrink-0 overflow-hidden",
                w.state === "completed" ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300" :
                w.state === "running" ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_20%,transparent)] border-[var(--chat-accent)] text-[var(--chat-accent)]" :
                w.state === "failed" ? "bg-red-500/20 border-red-500/40 text-red-300" :
                cn(theme.bg, theme.border, theme.text),
              )}>
                <PioneerPortrait role={role} />
              </div>

              <div className="flex-1 min-w-0">
                <span className="text-[11px] font-semibold text-[var(--chat-text)] mr-2">{w.pioneer_name}</span>
                <span className="text-[11px] text-[var(--chat-muted)] truncate">{w.task?.slice(0, 60)}{(w.task?.length ?? 0) > 60 ? "…" : ""}</span>
              </div>

              <div className="flex items-center gap-1 flex-shrink-0">
                <span className="text-[10px] text-[var(--chat-muted)] opacity-70">{String(i + 1).padStart(2, "0")}</span>
                <svg className="w-3 h-3 text-[var(--chat-muted)] opacity-40 group-hover:opacity-80 transition-opacity" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7"/>
                </svg>
              </div>

              <div
                className="absolute left-12 bottom-full mb-1.5 z-50 hidden group-hover:block w-64 rounded-lg bg-[var(--chat-surface)] border border-[var(--chat-border)] px-3 py-2.5 pointer-events-none"
                style={{ boxShadow: "var(--elev-2)" }}
              >
                <p className="text-[11px] font-bold text-[var(--chat-text)] mb-1">{w.pioneer_full_name ?? w.pioneer_name} &mdash; {w.role}</p>
                {w.pioneer_motto && (
                  <p className="text-[10px] italic text-[var(--chat-muted)] mb-1.5">&ldquo;{w.pioneer_motto}&rdquo;</p>
                )}
                <p className="text-[11px] text-[var(--chat-text)] opacity-80 leading-relaxed">{w.task}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
