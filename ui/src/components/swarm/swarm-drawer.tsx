"use client";

import { useCallback, useEffect } from "react";
import { cn } from "@/lib/utils/cn";
import { useSwarmStore } from "@/lib/stores/swarm-store";
import { AgentIdCard } from "./agent-id-card";
import { AgentRoster } from "./agent-roster";
import { AgentDock } from "./agent-dock";

/**
 * SwarmDrawer — slides in from the right over the chat when a swarm is active.
 * Orchestrates the three theater phases:
 *   decomposing / spawning_card → AgentIdCard per worker
 *   roster                      → AgentRoster grid
 *   working / synthesizing      → AgentDock (live status pills)
 *   complete / idle             → auto-dismiss
 */
export function SwarmDrawer() {
  const { active, theaterPhase, workers, latestCard, phaseName, setLatestCard, setTheaterPhase, setActive } =
    useSwarmStore();

  // Auto-dismiss the drawer when the swarm completes
  useEffect(() => {
    if (theaterPhase === "complete") {
      const t = setTimeout(() => {
        setActive(false);
        setTheaterPhase("idle");
      }, 2000);
      return () => clearTimeout(t);
    }
  }, [theaterPhase, setActive, setTheaterPhase]);

  // After roster reveal, auto-advance to the working checklist view (2s hold)
  useEffect(() => {
    if (theaterPhase === "roster") {
      const t = setTimeout(() => setTheaterPhase("working"), 2000);
      return () => clearTimeout(t);
    }
  }, [theaterPhase, setTheaterPhase]);

  // Stable callback so AgentIdCard's useEffect doesn't re-fire on every render
  const handleCardDone = useCallback(() => {
    setLatestCard(null);
    setTheaterPhase("roster");
  }, [setLatestCard, setTheaterPhase]);

  const visible = active && theaterPhase !== "idle";

  return (
    <div
      aria-hidden={!visible}
      className={cn(
        "absolute inset-y-0 right-0 z-40 w-96 flex flex-col",
        "bg-[var(--chat-bg)] border-l border-white/8",
        "shadow-2xl transition-transform duration-500 ease-[cubic-bezier(.32,1.4,.64,1)]",
        visible ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/8 flex-shrink-0">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        <span className="text-xs font-semibold text-white/70 tracking-wide uppercase">Swarm Active</span>
        <span className="ml-auto text-[10px] text-white/30">{workers.length} pioneer{workers.length !== 1 ? "s" : ""}</span>
      </div>

      {/* Phase label */}
      <div className="px-4 pt-3 pb-1 flex-shrink-0">
        <p className="text-[11px] text-white/40 uppercase tracking-widest">{phaseName || phaseLabel(theaterPhase)}</p>
      </div>

      {/* Main theater area */}
      <div className="flex-1 relative overflow-hidden">
        {/* ID card drop-in — shown when spawning_card */}
        {theaterPhase === "spawning_card" && latestCard && (
          <AgentIdCard
            key={latestCard.worker_id}
            worker={latestCard}
            onDone={handleCardDone}
          />
        )}

        {/* Roster grid */}
        {theaterPhase === "roster" && (
          <AgentRoster workers={workers} />
        )}

        {/* Working / synthesizing: agent dock */}
        {(theaterPhase === "working" || theaterPhase === "synthesizing") && (
          <div className="flex flex-col h-full">
            <AgentDock workers={workers} />
            <div className="flex-1 overflow-y-auto px-4 py-2 space-y-1">
              {workers.map((w) => (
                <div key={w.worker_id} className="flex items-start gap-2 text-[11px]">
                  <span
                    className={cn(
                      "mt-0.5 font-bold w-5 flex-shrink-0",
                      w.state === "completed" ? "text-emerald-400" :
                      w.state === "running" ? "text-[var(--chat-accent)]" :
                      w.state === "failed" ? "text-red-400" : "text-white/20",
                    )}
                  >
                    {w.state === "completed" ? "[x]" : w.state === "running" ? "[~]" : "[ ]"}
                  </span>
                  <span className="text-white/50 leading-snug">{w.task}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Decomposing: simple spinner */}
        {theaterPhase === "decomposing" && (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-white/20 border-t-[var(--chat-accent)] animate-spin" />
            <p className="text-xs text-white/40">Decomposing task&hellip;</p>
          </div>
        )}
      </div>

      {/* Bottom close strip */}
      <button
        onClick={() => { setActive(false); setTheaterPhase("idle"); }}
        className="flex-shrink-0 px-4 py-2.5 text-[10px] text-white/25 hover:text-white/50 transition-colors border-t border-white/8 text-center"
      >
        dismiss
      </button>
    </div>
  );
}

function phaseLabel(phase: string) {
  const MAP: Record<string, string> = {
    idle: "Idle",
    decomposing: "Decomposing",
    spawning_card: "Deploying pioneer",
    roster: "Assembling swarm",
    working: "Working",
    synthesizing: "Synthesizing",
    complete: "Complete",
  };
  return MAP[phase] ?? phase;
}
