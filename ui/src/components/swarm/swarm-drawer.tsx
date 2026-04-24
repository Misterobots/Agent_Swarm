"use client";

import { useCallback, useEffect, useRef } from "react";
import { cn } from "@/lib/utils/cn";
import { useSwarmStore } from "@/lib/stores/swarm-store";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import { AgentIdCard } from "./agent-id-card";
import { AgentRoster } from "./agent-roster";
import { AgentDock } from "./agent-dock";
import { PioneerPortrait } from "./pioneer-portrait";
import type { SwarmWorker } from "@/types/chat";

const ROLE_THEME: Record<string, { text: string; bg: string; border: string; stripe: string }> = {
  researcher: { text: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/30",   stripe: "bg-amber-400" },
  architect:  { text: "text-blue-400",    bg: "bg-blue-500/10",    border: "border-blue-500/30",    stripe: "bg-blue-400" },
  coder:      { text: "text-violet-400",  bg: "bg-violet-500/10",  border: "border-violet-500/30",  stripe: "bg-violet-400" },
  devops:     { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30", stripe: "bg-emerald-400" },
  analyst:    { text: "text-cyan-400",    bg: "bg-cyan-500/10",    border: "border-cyan-500/30",    stripe: "bg-cyan-400" },
  verifier:   { text: "text-rose-400",    bg: "bg-rose-500/10",    border: "border-rose-500/30",    stripe: "bg-rose-400" },
};
const DEFAULT_THEME = { text: "text-white/60", bg: "bg-white/5", border: "border-white/20", stripe: "bg-white/40" };

function WorkerDetailPanel({ worker, onClose }: { worker: SwarmWorker; onClose: () => void }) {
  const role = worker.role?.toLowerCase() ?? "";
  const theme = ROLE_THEME[role] ?? DEFAULT_THEME;

  return (
    <div className="absolute inset-0 z-10 flex flex-col bg-[var(--chat-bg)] animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/8 flex-shrink-0">
        <button
          onClick={onClose}
          className="flex items-center gap-1.5 text-white/40 hover:text-white/70 transition-colors text-[11px]"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7"/>
          </svg>
          Back
        </button>
        <div className="flex items-center gap-2 ml-auto">
          <span className={cn("w-1.5 h-1.5 rounded-full",
            worker.state === "completed" ? "bg-emerald-400" :
            worker.state === "running" ? "bg-[var(--chat-accent)] animate-pulse" :
            worker.state === "failed" ? "bg-red-400" : "bg-white/20"
          )} />
          <span className="text-[10px] text-white/30 uppercase tracking-widest">{worker.state}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Pioneer hero */}
        <div className={cn("px-6 py-6 flex items-center gap-4 border-b border-white/6", theme.bg)}>
          <div className={cn(
            "w-16 h-16 rounded-full border-2 overflow-hidden flex-shrink-0",
            theme.border, theme.text,
          )}>
            <PioneerPortrait role={role} />
          </div>
          <div className="min-w-0">
            <p className="font-black text-white text-base leading-tight">
              {worker.pioneer_full_name ?? worker.pioneer_name}
            </p>
            <p className={cn("text-[11px] mt-0.5 uppercase tracking-[0.16em] font-bold", theme.text)}>
              {worker.role}
            </p>
            {worker.pioneer_motto && (
              <p className="text-white/35 text-[10px] mt-1.5 italic leading-snug">
                &ldquo;{worker.pioneer_motto}&rdquo;
              </p>
            )}
          </div>
        </div>

        {/* Task assigned */}
        <div className="px-5 py-4 border-b border-white/6">
          <p className="text-[10px] font-black tracking-[0.2em] text-white/30 uppercase mb-2">Task Assigned</p>
          <p className="text-[13px] text-white/80 leading-relaxed">{worker.task}</p>
        </div>

        {/* Output / findings */}
        {worker.output ? (
          <div className="px-5 py-4">
            <p className="text-[10px] font-black tracking-[0.2em] text-white/30 uppercase mb-2">Findings</p>
            <p className="text-[12px] text-white/65 leading-relaxed whitespace-pre-wrap">{worker.output}</p>
          </div>
        ) : worker.state === "running" ? (
          <div className="px-5 py-4 flex items-center gap-2 text-[12px] text-white/35">
            <div className="w-3.5 h-3.5 rounded-full border-2 border-white/20 border-t-[var(--chat-accent)] animate-spin flex-shrink-0" />
            Researching&hellip;
          </div>
        ) : worker.state === "pending" ? (
          <div className="px-5 py-4 text-[12px] text-white/25">Queued — waiting for previous workers</div>
        ) : null}
      </div>
    </div>
  );
}

function WorkerRow({ worker, selected, onClick }: { worker: SwarmWorker; selected: boolean; onClick: () => void }) {
  const role = worker.role?.toLowerCase() ?? "";
  const theme = ROLE_THEME[role] ?? DEFAULT_THEME;

  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3 px-4 py-3 text-left transition-all",
        "border-b border-white/5 hover:bg-white/4",
        selected && "bg-white/5",
      )}
    >
      {/* State indicator stripe */}
      <div className={cn(
        "w-0.5 h-8 rounded-full flex-shrink-0",
        worker.state === "completed" ? "bg-emerald-400" :
        worker.state === "running" ? "bg-[var(--chat-accent)] animate-pulse" :
        worker.state === "failed" ? "bg-red-400" : "bg-white/10",
      )} />

      {/* Mini portrait */}
      <div className={cn(
        "w-9 h-9 rounded-full border overflow-hidden flex-shrink-0",
        theme.bg, theme.border, theme.text,
      )}>
        <PioneerPortrait role={role} />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-[12px] font-bold text-white/80 truncate">{worker.pioneer_name}</span>
          <span className={cn("text-[9px] uppercase tracking-wide flex-shrink-0", theme.text)}>{worker.role}</span>
        </div>
        <p className="text-[10px] text-white/35 truncate mt-0.5">{worker.task}</p>
      </div>

      {/* State badge + chevron */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {worker.state === "completed" && <span className="text-emerald-400 text-[10px] font-bold">✓</span>}
        {worker.state === "running" && <span className="text-[var(--chat-accent)] text-[10px] animate-pulse">●</span>}
        {worker.state === "failed" && <span className="text-red-400 text-[10px]">✗</span>}
        {worker.state === "pending" && <span className="text-white/20 text-[10px]">○</span>}
        <svg className="w-3 h-3 text-white/20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7"/>
        </svg>
      </div>
    </button>
  );
}

/**
 * SwarmPanelContent — props-driven inner body shared by drawer, mobile sheet, and popup page.
 */
export interface SwarmPanelContentProps {
  theaterPhase: string;
  phaseName: string;
  workers: SwarmWorker[];
  latestCard: SwarmWorker | null;
  selectedWorkerId: string | null;
  onCardDone: () => void;
  onSelectWorker: (id: string | null) => void;
  onPhaseChange: (phase: import("@/lib/stores/swarm-store").SwarmTheaterPhase) => void;
}

export function SwarmPanelContent({
  theaterPhase, phaseName, workers, latestCard,
  selectedWorkerId, onCardDone, onSelectWorker, onPhaseChange,
}: SwarmPanelContentProps) {
  const selectedWorker = selectedWorkerId ? workers.find((w) => w.worker_id === selectedWorkerId) : null;

  // Auto-advance roster → working after 2 s
  useEffect(() => {
    if (theaterPhase === "roster") {
      const t = setTimeout(() => onPhaseChange("working"), 2000);
      return () => clearTimeout(t);
    }
  }, [theaterPhase, onPhaseChange]);

  return (
    <>
      {/* Phase label */}
      <div className="px-4 pt-3 pb-1 flex-shrink-0">
        <p className="text-[11px] text-white/40 uppercase tracking-widest">
          {phaseName || phaseLabel(theaterPhase)}
        </p>
      </div>

      {/* Main theater area */}
      <div className="flex-1 relative overflow-hidden">
        {/* ID card drop-in */}
        {theaterPhase === "spawning_card" && latestCard && (
          <AgentIdCard key={latestCard.worker_id} worker={latestCard} onDone={onCardDone} />
        )}

        {/* Roster grid */}
        {theaterPhase === "roster" && <AgentRoster workers={workers} />}

        {/* Working / synthesizing / complete */}
        {(theaterPhase === "working" || theaterPhase === "synthesizing" || theaterPhase === "complete") && (
          <div className="relative h-full flex flex-col">
            {theaterPhase !== "complete" && (
              <AgentDock workers={workers} onSelect={onSelectWorker} />
            )}
            {theaterPhase === "complete" && (
              <div className="flex items-center gap-2 px-4 py-2.5 bg-emerald-500/8 border-b border-emerald-500/20 flex-shrink-0">
                <span className="text-emerald-400 text-sm">✓</span>
                <span className="text-[11px] text-emerald-400/80 font-semibold">
                  All {workers.filter(w => w.state === "completed").length} pioneers complete
                  {workers.filter(w => w.state === "failed").length > 0 &&
                    ` · ${workers.filter(w => w.state === "failed").length} failed`}
                </span>
              </div>
            )}
            <div className="flex-1 overflow-y-auto">
              {workers.map((w) => (
                <WorkerRow
                  key={w.worker_id}
                  worker={w}
                  selected={selectedWorkerId === w.worker_id}
                  onClick={() => onSelectWorker(selectedWorkerId === w.worker_id ? null : w.worker_id)}
                />
              ))}
            </div>
            {selectedWorker && (
              <WorkerDetailPanel worker={selectedWorker} onClose={() => onSelectWorker(null)} />
            )}
          </div>
        )}

        {/* Decomposing spinner */}
        {theaterPhase === "decomposing" && (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-white/20 border-t-[var(--chat-accent)] animate-spin" />
            <p className="text-xs text-white/40">Decomposing task&hellip;</p>
          </div>
        )}
      </div>
    </>
  );
}

// ─── Mobile full-screen bottom sheet ────────────────────────────────────────

function SwarmMobilePanel() {
  const {
    active, theaterPhase, phaseName, workers, latestCard, selectedWorkerId,
    dismissed, setDismissed, setLatestCard, setTheaterPhase, setSelectedWorker,
  } = useSwarmStore();

  const handleCardDone = useCallback(() => {
    setLatestCard(null);
    setTheaterPhase("roster");
  }, [setLatestCard, setTheaterPhase]);

  const visible = active && theaterPhase !== "idle" && !dismissed;

  return (
    <>
      {/* Backdrop — tap to collapse */}
      {visible && (
        <div
          className="fixed inset-0 z-40 bg-black/60"
          onClick={() => setDismissed(true)}
          aria-hidden="true"
        />
      )}

      {/* Full-screen panel — slides up from bottom */}
      <div
        aria-hidden={!visible}
        className={cn(
          "fixed inset-x-0 top-0 bottom-0 z-50 flex flex-col",
          "bg-[var(--chat-bg)] rounded-t-3xl",
          "shadow-[0_-24px_80px_rgba(0,0,0,0.7)]",
          "transition-transform duration-500 ease-[cubic-bezier(.32,1.4,.64,1)]",
          visible ? "translate-y-0" : "translate-y-full",
        )}
      >
        {/* Drag handle */}
        <div className="flex-shrink-0 flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-white/20" />
        </div>

        {/* Header */}
        <div className="flex items-center gap-2 px-5 py-3 border-b border-white/8 flex-shrink-0">
          <div className={cn(
            "w-1.5 h-1.5 rounded-full",
            theaterPhase === "complete" ? "bg-emerald-400" : "bg-emerald-400 animate-pulse",
          )} />
          <span className="text-xs font-semibold text-white/70 tracking-wide uppercase">
            {theaterPhase === "complete" ? "Swarm Complete" : "Swarm Active"}
          </span>
          <span className="text-[10px] text-white/30 ml-1">
            {workers.length} pioneer{workers.length !== 1 ? "s" : ""}
          </span>
          <button
            onClick={() => setDismissed(true)}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] text-white/40 hover:text-white/70 hover:bg-white/5 transition-all"
            aria-label="Collapse swarm panel"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7"/>
            </svg>
            Collapse
          </button>
        </div>

        <SwarmPanelContent
          theaterPhase={theaterPhase}
          phaseName={phaseName}
          workers={workers}
          latestCard={latestCard}
          selectedWorkerId={selectedWorkerId}
          onCardDone={handleCardDone}
          onSelectWorker={setSelectedWorker}
          onPhaseChange={setTheaterPhase}
        />

        {/* Safe-area spacer */}
        <div className="flex-shrink-0 h-[env(safe-area-inset-bottom)]" />
      </div>
    </>
  );
}

// ─── Desktop side drawer ──────────────────────────────────────────────────────

function SwarmDesktopDrawer() {
  const {
    active, theaterPhase, phaseName, workers, latestCard, selectedWorkerId,
    dismissed, popoutOpen, setDismissed, setPopoutOpen, setLatestCard, setTheaterPhase, setSelectedWorker,
  } = useSwarmStore();

  const popupRef = useRef<Window | null>(null);

  const handleCardDone = useCallback(() => {
    setLatestCard(null);
    setTheaterPhase("roster");
  }, [setLatestCard, setTheaterPhase]);

  // Poll popup closed state
  useEffect(() => {
    if (!popoutOpen) return;
    const id = setInterval(() => {
      if (popupRef.current?.closed) {
        setPopoutOpen(false);
        setDismissed(false);
        popupRef.current = null;
      }
    }, 1000);
    return () => clearInterval(id);
  }, [popoutOpen, setPopoutOpen, setDismissed]);

  const handlePopout = useCallback(() => {
    const popup = window.open("/swarm", "hive-swarm-panel", "width=580,height=820,resizable=yes");
    if (popup) {
      popupRef.current = popup;
      setPopoutOpen(true);
      setDismissed(true);
    }
  }, [setPopoutOpen, setDismissed]);

  const visible = active && theaterPhase !== "idle" && !dismissed;

  return (
    <div
      aria-hidden={!visible}
      className={cn(
        "absolute inset-y-0 right-0 z-40 w-[min(540px,48vw)] flex flex-col",
        "bg-[var(--chat-bg)] border-l border-white/8",
        "shadow-[-24px_0_80px_rgba(0,0,0,0.5)] transition-transform duration-500 ease-[cubic-bezier(.32,1.4,.64,1)]",
        visible ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/8 flex-shrink-0">
        <div className={cn(
          "w-1.5 h-1.5 rounded-full",
          theaterPhase === "complete" ? "bg-emerald-400" : "bg-emerald-400 animate-pulse",
        )} />
        <span className="text-xs font-semibold text-white/70 tracking-wide uppercase">
          {theaterPhase === "complete" ? "Swarm Complete" : "Swarm Active"}
        </span>
        <span className="ml-auto text-[10px] text-white/30">{workers.length} pioneer{workers.length !== 1 ? "s" : ""}</span>

        {/* Popout */}
        <button
          onClick={handlePopout}
          className="ml-2 p-1 rounded text-white/25 hover:text-white/60 transition-colors"
          title="Open in separate window"
          aria-label="Open swarm panel in new window"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
          </svg>
        </button>

        {/* Collapse */}
        <button
          onClick={() => setDismissed(true)}
          className="ml-1 p-1 rounded text-white/25 hover:text-white/60 transition-colors"
          title="Collapse panel"
          aria-label="Collapse swarm panel"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7"/>
          </svg>
        </button>
      </div>

      {/* Popout placeholder */}
      {popoutOpen ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center">
          <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
            <svg className="w-5 h-5 text-white/40" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-white/60">In external window</p>
            <p className="text-[11px] text-white/30 mt-1">Swarm panel is open in a separate window</p>
          </div>
          <button
            onClick={() => {
              popupRef.current?.close();
              popupRef.current = null;
              setPopoutOpen(false);
              setDismissed(false);
            }}
            className="px-4 py-2 rounded-lg text-[11px] text-white/50 border border-white/10 hover:bg-white/5 transition-all"
          >
            Close &amp; Restore here
          </button>
        </div>
      ) : (
        <SwarmPanelContent
          theaterPhase={theaterPhase}
          phaseName={phaseName}
          workers={workers}
          latestCard={latestCard}
          selectedWorkerId={selectedWorkerId}
          onCardDone={handleCardDone}
          onSelectWorker={setSelectedWorker}
          onPhaseChange={setTheaterPhase}
        />
      )}
    </div>
  );
}

// ─── Public export ────────────────────────────────────────────────────────────

/**
 * SwarmDrawer — mobile → full-screen bottom sheet; desktop → side panel.
 */
export function SwarmDrawer() {
  const { isMobile } = useIsMobile();
  return isMobile ? <SwarmMobilePanel /> : <SwarmDesktopDrawer />;
}

function phaseLabel(phase: string) {
  const MAP: Record<string, string> = {
    idle: "Idle",
    decomposing: "Decomposing",
    spawning_card: "Deploying pioneer",
    roster: "Assembling swarm",
    working: "Working",
    synthesizing: "Synthesizing findings",
    complete: "Review findings",
  };
  return MAP[phase] ?? phase;
}
