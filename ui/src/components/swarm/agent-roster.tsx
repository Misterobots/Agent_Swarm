"use client";

import { useEffect, useRef, useState } from "react";
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

const ROLE_VERB: Record<string, string> = {
  researcher: "Researching", architect: "Designing", coder: "Coding",
  devops: "Deploying", analyst: "Analyzing", verifier: "Verifying",
};

const ROLE_CLEARANCE: Record<string, string> = {
  researcher: "LEVEL 3", architect: "LEVEL 4", coder: "LEVEL 3",
  devops: "LEVEL 5", analyst: "LEVEL 3", verifier: "LEVEL 5",
};

/** Compact barcode from first 6 chars of worker_id */
function MiniBarcode({ seed }: { seed: string }) {
  const bars = Array.from({ length: 14 }, (_, i) => {
    const c = seed.charCodeAt(i % seed.length) ^ (i * 37);
    return (c % 5 === 0) ? 3 : (c % 3 === 0) ? 1.5 : 0.8;
  });
  return (
    <svg viewBox="0 0 40 10" className="w-10 h-2.5 opacity-25" xmlns="http://www.w3.org/2000/svg">
      {bars.reduce<{ x: number; els: React.ReactElement[] }>(
        ({ x, els }, w, i) => ({
          x: x + w + 0.5,
          els: [...els, i % 2 === 0
            ? <rect key={i} x={x} y={0} width={w} height={10} fill="currentColor" />
            : <rect key={i} x={x} y={0} width={w} height={10} fill="none" />],
        }),
        { x: 0, els: [] }
      ).els}
    </svg>
  );
}

interface AgentRosterProps {
  workers: SwarmWorker[];
  /** When set, only workers in this list are shown (others appear as ghosts). Used during badge spawning. */
  revealedIds?: string[];
}

export function AgentRoster({ workers, revealedIds }: AgentRosterProps) {
  // Track which cards should use the bounce-in animation vs stagger fade-in
  const prevRevealedRef = useRef<Set<string>>(new Set(revealedIds ?? []));
  const [justRevealed, setJustRevealed] = useState<Set<string>>(new Set());

  // When a new ID appears in revealedIds, mark it for the card-enter bounce animation
  useEffect(() => {
    if (!revealedIds) return;
    const newIds = revealedIds.filter((id) => !prevRevealedRef.current.has(id));
    if (newIds.length > 0) {
      setJustRevealed((s) => new Set([...s, ...newIds]));
      prevRevealedRef.current = new Set(revealedIds);
      // Clear "just revealed" after animation completes
      const t = setTimeout(() => setJustRevealed(new Set()), 700);
      return () => clearTimeout(t);
    }
  }, [revealedIds]);

  // Normal roster: stagger all workers in
  const [staggerVisible, setStaggerVisible] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (revealedIds) return; // skip stagger when in badge-spawning mode
    workers.forEach((w, i) => {
      setTimeout(() => setStaggerVisible((s) => new Set([...s, w.worker_id])), i * 120);
    });
  }, [workers, revealedIds]);

  const maxSlots = Math.max(workers.length, 3);
  const slots = workers.length >= maxSlots ? workers : [
    ...workers,
    ...Array.from({ length: maxSlots - workers.length }, (_, i) => ({
      worker_id: `ghost-${i}`, role: "", pioneer_name: "···", pioneer_motto: "",
      task: "", phase: "", state: "pending" as const,
    })),
  ];

  const isSpawning = !!revealedIds;

  return (
    <div className={cn(
      "flex flex-col items-center justify-center gap-4 w-full px-4",
      isSpawning ? "" : "h-full",
    )}>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 w-full max-w-sm">
        {slots.map((w) => {
          const isGhost = w.worker_id.startsWith("ghost-");
          const isRevealed = isSpawning ? (revealedIds!.includes(w.worker_id)) : staggerVisible.has(w.worker_id);
          const isNewlyRevealed = justRevealed.has(w.worker_id);
          const role = w.role?.toLowerCase() ?? "";
          const theme = ROLE_THEME[role] ?? DEFAULT_THEME;
          const isRunning = w.state === "running";
          const badgeNum = w.worker_id.replace(/[^a-z0-9]/gi, "").slice(-6).toUpperCase().padStart(6, "0");
          const stateLabel =
            isRunning ? (ROLE_VERB[role] ?? "Active") :
            w.state === "completed" ? "Done" :
            w.state === "failed" ? "Error" : "Queued";

          return (
            <div
              key={w.worker_id}
              className={cn(
                "flex flex-col rounded-lg overflow-hidden border transition-all",
                "bg-[var(--chat-panel)]",
                isGhost
                  ? "opacity-20 border-[var(--chat-border)]"
                  : isNewlyRevealed
                  ? "[animation:id-card-enter_0.55s_cubic-bezier(.32,1.4,.64,1)_forwards]"
                  : isRevealed
                  ? "opacity-100 translate-y-0 duration-300"
                  : "opacity-0 translate-y-3 duration-300",
                !isGhost && theme.border,
              )}
              style={!isGhost && isRunning && theme.accent
                ? { boxShadow: `0 0 0 1px ${theme.accent}35, 0 0 14px ${theme.accent}20` }
                : undefined}
            >
              {/* Holographic foil stripe */}
              {!isGhost && (
                <div
                  className="h-[3px] w-full flex-shrink-0"
                  style={{ background: `linear-gradient(90deg, transparent 0%, ${theme.accent} 20%, #fff 50%, ${theme.accent} 80%, transparent 100%)`, opacity: 0.75 }}
                />
              )}
              {isGhost && <div className="h-[3px] w-full bg-[var(--chat-border)] flex-shrink-0" />}

              {/* Org mini-header — role-colored tint */}
              {!isGhost && (
                <div
                  className="px-2 py-1 flex items-center justify-between flex-shrink-0"
                  style={{ background: `${theme.accent}14`, borderBottom: `1px solid ${theme.accent}20` }}
                >
                  <span className="text-[6px] font-black tracking-[0.2em] text-white/40 uppercase">Hive Mind</span>
                  <span className="text-[5px] font-mono tracking-widest" style={{ color: `${theme.accent}80` }}>PIONEER</span>
                </div>
              )}

              {/* Photo + Info — horizontal ID-card layout */}
              {!isGhost ? (
                <div className="flex gap-1.5 px-2 pt-2 pb-1.5">
                  {/* Photo */}
                  <div
                    className={cn(
                      "w-9 h-11 rounded-sm border overflow-hidden flex-shrink-0",
                      theme.bg, theme.border, theme.text,
                    )}
                    style={{ boxShadow: `0 0 8px ${theme.accent}25` }}
                  >
                    <PioneerPortrait role={role} />
                  </div>

                  {/* Info column */}
                  <div className="flex flex-col justify-between min-w-0 flex-1 py-0.5">
                    {/* Name */}
                    <p className="text-[9px] font-bold text-[var(--chat-text)] truncate leading-tight">
                      {w.pioneer_name}
                    </p>
                    {/* Role badge */}
                    <div
                      className="inline-flex items-center rounded-sm px-1 py-0.5 self-start mt-0.5"
                      style={{ background: `${theme.accent}18`, border: `1px solid ${theme.accent}40` }}
                    >
                      <span
                        className="text-[6.5px] font-bold uppercase tracking-wider"
                        style={{ color: theme.accent }}
                      >
                        {w.role}
                      </span>
                    </div>
                    {/* Clearance */}
                    <p className="text-[6px] font-mono mt-0.5" style={{ color: `${theme.accent}70` }}>
                      {ROLE_CLEARANCE[role] ?? "LEVEL 1"}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="h-12 flex items-center justify-center">
                  <span className="text-[8px] text-[var(--chat-muted)] opacity-30">···</span>
                </div>
              )}

              {/* Status footer */}
              {!isGhost && (
                <div
                  className="px-2 py-1.5 border-t flex items-center justify-between flex-shrink-0"
                  style={{ borderColor: `${theme.accent}18`, background: `${theme.accent}06` }}
                >
                  <div className="flex items-center gap-1">
                    <span
                      className={cn("w-1 h-1 rounded-full flex-shrink-0",
                        w.state === "completed" ? "bg-emerald-400" :
                        isRunning ? cn(theme.stripe, "animate-pulse") :
                        w.state === "failed" ? "bg-red-400" : "bg-[var(--chat-muted)]"
                      )}
                    />
                    <span
                      className={cn(
                        "text-[6px] uppercase tracking-[0.14em] font-semibold truncate",
                        isRunning ? theme.text : "text-[var(--chat-muted)]",
                      )}
                    >
                      {stateLabel}
                    </span>
                  </div>
                  <div className={cn("flex items-center", theme.text)}>
                    <MiniBarcode seed={badgeNum} />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {!isSpawning && (
        <p className="text-[11px] text-[var(--chat-muted)] animate-pulse">Assembling swarm&hellip;</p>
      )}
    </div>
  );
}
