"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils/cn";
import { useSwarmStore } from "@/lib/stores/swarm-store";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import { AgentIdCard } from "./agent-id-card";
import { AgentRoster } from "./agent-roster";
import { AgentDock } from "./agent-dock";
import { PioneerPortrait } from "./pioneer-portrait";
import { PIONEER_BIOS } from "@/lib/data/pioneer-bios";
import type { SwarmWorker } from "@/types/chat";

const ROLE_THEME: Record<string, { text: string; bg: string; border: string; stripe: string }> = {
  researcher: { text: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/30",   stripe: "bg-amber-400" },
  architect:  { text: "text-blue-400",    bg: "bg-blue-500/10",    border: "border-blue-500/30",    stripe: "bg-blue-400" },
  coder:      { text: "text-violet-400",  bg: "bg-violet-500/10",  border: "border-violet-500/30",  stripe: "bg-violet-400" },
  devops:     { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30", stripe: "bg-emerald-400" },
  analyst:    { text: "text-cyan-400",    bg: "bg-cyan-500/10",    border: "border-cyan-500/30",    stripe: "bg-cyan-400" },
  verifier:   { text: "text-rose-400",    bg: "bg-rose-500/10",    border: "border-rose-500/30",    stripe: "bg-rose-400" },
};
const DEFAULT_THEME = { text: "text-[var(--chat-muted)]", bg: "bg-[var(--chat-soft)]", border: "border-[var(--chat-border)]", stripe: "bg-[var(--chat-muted)]" };

/** Full detail view — rendered as a normal scrollable column (no absolute overlay) */
function WorkerDetailContent({ worker, onClose }: { worker: SwarmWorker; onClose: () => void }) {
  const role = worker.role?.toLowerCase() ?? "";
  const theme = ROLE_THEME[role] ?? DEFAULT_THEME;
  const [bioOpen, setBioOpen] = useState(false);

  return (
    <div className="flex flex-col h-full">
      {/* Mini close header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--chat-border)] flex-shrink-0">
        <span className={cn("text-[10px] font-bold uppercase tracking-[0.18em]", theme.text)}>{worker.role}</span>
        <button
          onClick={onClose}
          className="p-0.5 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
          aria-label="Close detail"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Pioneer hero */}
        <div className={cn("px-3 py-4 flex flex-col items-center gap-2 border-b border-[var(--chat-border)]", theme.bg)}>
          <div className={cn(
            "w-14 h-14 rounded-full border-2 overflow-hidden flex-shrink-0",
            theme.border, theme.text,
          )}>
            <PioneerPortrait role={role} />
          </div>
          <div className="text-center min-w-0 w-full">
            <p className="font-black text-[var(--chat-text)] text-[13px] leading-tight truncate px-1">
              {worker.pioneer_full_name ?? worker.pioneer_name}
            </p>
            <div className="flex items-center gap-1.5 justify-center mt-1.5">
              <span className={cn(
                "w-1.5 h-1.5 rounded-full flex-shrink-0",
                worker.state === "completed" ? "bg-emerald-400" :
                worker.state === "running" ? "bg-[var(--chat-accent)] animate-pulse" :
                worker.state === "failed" ? "bg-red-400" : "bg-[var(--chat-muted)]"
              )} />
              <span className="text-[9px] text-[var(--chat-muted)] uppercase tracking-widest">{worker.state}</span>
            </div>
            {worker.pioneer_motto && (
              <p className="text-[var(--chat-muted)] text-[9px] mt-1.5 italic leading-snug px-1">
                &ldquo;{worker.pioneer_motto}&rdquo;
              </p>
            )}
          </div>
        </div>

        {/* Pioneer bio + history + Wikipedia — collapsible */}
        {(() => {
          const bio = PIONEER_BIOS[worker.pioneer_name ?? ""];
          if (!bio) return null;
          return (
            <div className="border-b border-[var(--chat-border)]">
              {/* Accordion toggle */}
              <button
                onClick={() => setBioOpen(o => !o)}
                className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-[var(--chat-soft)] transition-colors"
              >
                <span className="text-[8px] font-black tracking-[0.2em] text-[var(--chat-muted)] uppercase">
                  Pioneer Profile
                </span>
                <svg
                  className={cn("w-3 h-3 text-[var(--chat-muted)] transition-transform duration-200", bioOpen && "rotate-180")}
                  fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Collapsible body */}
              {bioOpen && (
                <>
                  <div className="px-3 pb-3 border-t border-[var(--chat-border)]">
                    <p className="text-[8px] font-black tracking-[0.2em] text-[var(--chat-muted)] uppercase mt-2.5 mb-1.5">About</p>
                    <p className="text-[11px] text-[var(--chat-muted)] leading-relaxed">{bio.bio}</p>
                  </div>
                  <div className="px-3 pb-3 border-t border-[var(--chat-border)]">
                    <p className="text-[8px] font-black tracking-[0.2em] text-[var(--chat-muted)] uppercase mt-2.5 mb-1.5">Historical Context</p>
                    <p className="text-[10px] text-[var(--chat-muted)] leading-relaxed opacity-80">{bio.historical_context}</p>
                  </div>
                  <div className="px-3 pb-3 border-t border-[var(--chat-border)]">
                    <div className="mt-2.5">
                      <a
                        href={bio.wikipedia_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={cn(
                          "inline-flex items-center gap-1.5 text-[9px] font-semibold px-2 py-1 rounded-sm transition-opacity hover:opacity-70",
                          theme.text, theme.bg, theme.border, "border",
                        )}
                      >
                        <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15v-4H7l5-8v4h4l-5 8z" />
                        </svg>
                        Learn more on Wikipedia
                      </a>
                    </div>
                  </div>
                </>
              )}
            </div>
          );
        })()}

        {/* Task */}
        <div className="px-3 py-3 border-b border-[var(--chat-border)]">
          <p className="text-[8px] font-black tracking-[0.2em] text-[var(--chat-muted)] uppercase mb-1.5">Task</p>
          <p className="text-[11px] text-[var(--chat-text)] leading-relaxed">{worker.task}</p>
        </div>

        {/* Output / findings */}
        {worker.output ? (
          <div className="px-3 py-3">
            <p className="text-[8px] font-black tracking-[0.2em] text-[var(--chat-muted)] uppercase mb-1.5">Findings</p>
            <p className="text-[11px] text-[var(--chat-muted)] leading-relaxed whitespace-pre-wrap break-words">{worker.output}</p>
          </div>
        ) : worker.state === "running" ? (
          <div className="px-3 py-3 flex items-center gap-2 text-[11px] text-[var(--chat-muted)]">
            <div className="w-3 h-3 rounded-full border-2 border-[var(--chat-border)] border-t-[var(--chat-accent)] animate-spin flex-shrink-0" />
            Researching&hellip;
          </div>
        ) : worker.state === "pending" ? (
          <div className="px-3 py-3 text-[11px] text-[var(--chat-muted)]">Queued &mdash; waiting</div>
        ) : null}
      </div>
    </div>
  );
}

function WorkerRow({ worker, expanded, onClick }: { worker: SwarmWorker; expanded: boolean; onClick: () => void }) {
  const role = worker.role?.toLowerCase() ?? "";
  const theme = ROLE_THEME[role] ?? DEFAULT_THEME;

  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3 px-4 py-3 text-left transition-all",
        "hover:bg-[var(--chat-soft)]",
        expanded && "bg-[var(--chat-soft)]",
      )}
    >
      {/* State indicator stripe — role color when running */}
      <div className={cn(
        "w-0.5 h-8 rounded-full flex-shrink-0",
        worker.state === "completed" ? "bg-emerald-400" :
        worker.state === "running" ? cn(theme.stripe, "animate-pulse") :
        worker.state === "failed" ? "bg-red-400" : "bg-[var(--chat-border)]",
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
          <span className="text-[12px] font-bold text-[var(--chat-text)] truncate">{worker.pioneer_name}</span>
          <span className={cn("text-[9px] uppercase tracking-wide flex-shrink-0", theme.text)}>{worker.role}</span>
        </div>
        <p className="text-[10px] text-[var(--chat-muted)] truncate mt-0.5">{worker.task}</p>
      </div>

      {/* State badge + chevron */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {worker.state === "completed" && <span className="text-emerald-400 text-[10px] font-bold">✓</span>}
        {worker.state === "running" && <span className={cn("text-[10px] animate-pulse", theme.text)}>●</span>}
        {worker.state === "failed" && <span className="text-red-400 text-[10px]">✗</span>}
        {worker.state === "pending" && <span className="text-[var(--chat-muted)] text-[10px]">○</span>}
        <svg
          className={cn("w-3 h-3 text-[var(--chat-muted)] transition-transform duration-300", expanded && "rotate-90")}
          fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
        >
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
  const revealedWorkerIds = useSwarmStore((s) => s.revealedWorkerIds);
  const badgeQueue = useSwarmStore((s) => s.badgeQueue);
  const phaseNameMap = useSwarmStore((s) => s.phaseNameMap);

  // Workers NOT in the current badge-spawn batch — shown during spawning/decomposing as history
  const currentBatchIds = new Set([
    ...(latestCard ? [latestCard.worker_id] : []),
    ...badgeQueue.map((w) => w.worker_id),
    ...revealedWorkerIds,
  ]);
  const previousPhaseWorkers = workers.filter((w) => !currentBatchIds.has(w.worker_id));

  // Group all workers by their phase field for the timeline working list
  const phaseGroups = workers.reduce<Record<string, SwarmWorker[]>>((acc, w) => {
    const key = w.phase ?? "1";
    if (!acc[key]) acc[key] = [];
    acc[key].push(w);
    return acc;
  }, {});
  const sortedPhaseKeys = Object.keys(phaseGroups).sort((a, b) => Number(a) - Number(b));
  const showPhaseDividers = sortedPhaseKeys.length > 1;

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
        <p className="text-[11px] text-[var(--chat-muted)] uppercase tracking-widest">
          {phaseName || phaseLabel(theaterPhase)}
        </p>
      </div>

      {/* Main theater area */}
      <div className="flex-1 relative overflow-hidden">
        {/* ID card drop-in + growing roster below */}
        {theaterPhase === "spawning_card" && latestCard && (
          <div className="flex flex-col h-full">
            {/* Badge takes the upper portion */}
            <div className={cn(
              "flex items-center justify-center min-h-0 overflow-hidden",
              previousPhaseWorkers.length > 0 ? "flex-[3]" : "flex-1",
            )}>
              <AgentIdCard key={latestCard.worker_id} worker={latestCard} onDone={onCardDone} />
            </div>
            {/* Partial roster — revealed workers only, grows as badges complete */}
            {revealedWorkerIds.length > 0 && (
              <div className="flex-shrink-0 pb-2 border-t border-[var(--chat-border)]">
                <AgentRoster workers={workers} revealedIds={revealedWorkerIds} />
              </div>
            )}
            {/* Previous phase workers — scrollable history panel */}
            {previousPhaseWorkers.length > 0 && (
              <div className="flex-shrink-0 overflow-y-auto border-t border-[var(--chat-border)] max-h-[35%]">
                <div className="flex items-center gap-2 px-4 py-1.5 sticky top-0 bg-[var(--chat-surface)] border-b border-[var(--chat-border)]">
                  <div className="h-px flex-1 bg-[var(--chat-border)]" />
                  <span className="text-[7px] font-black tracking-[0.25em] text-[var(--chat-muted)] uppercase flex-shrink-0">Prior phase activity</span>
                  <div className="h-px flex-1 bg-[var(--chat-border)]" />
                </div>
                {previousPhaseWorkers.map((w) => (
                  <div key={w.worker_id} className="border-b border-[var(--chat-border)]">
                    <WorkerRow
                      worker={w}
                      expanded={selectedWorkerId === w.worker_id}
                      onClick={() => onSelectWorker(selectedWorkerId === w.worker_id ? null : w.worker_id)}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Roster grid */}
        {theaterPhase === "roster" && <AgentRoster workers={workers} />}

        {/* Working / synthesizing / complete */}
        {(theaterPhase === "working" || theaterPhase === "synthesizing" || theaterPhase === "complete") && (
          <div className="h-full flex flex-col overflow-hidden">
            {/* AgentDock + complete banner: full width, above the split */}
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

            {/* Horizontal split: list left, detail right */}
            <div className="flex-1 flex flex-row overflow-hidden">
              {/* Worker list — grouped by phase with timeline dividers */}
              <div className="flex-1 min-w-0 min-h-0 overflow-y-auto">
                {showPhaseDividers ? (
                  sortedPhaseKeys.map((phaseKey) => {
                    const group = phaseGroups[phaseKey];
                    const label = phaseNameMap[phaseKey] || `Phase ${phaseKey}`;
                    const doneCount = group.filter((w) => w.state === "completed").length;
                    return (
                      <div key={phaseKey}>
                        {/* Phase timeline divider */}
                        <div className="flex items-center gap-2 px-4 py-1.5 border-b border-[var(--chat-border)] bg-[var(--chat-soft)]/40 sticky top-0 z-10">
                          <span className="w-1.5 h-1.5 rounded-full bg-[var(--chat-muted)] flex-shrink-0" />
                          <span className="text-[8px] font-black tracking-[0.2em] text-[var(--chat-muted)] uppercase truncate">
                            {label}
                          </span>
                          <span className="text-[8px] text-[var(--chat-muted)] flex-shrink-0 ml-auto">
                            {doneCount}/{group.length} done
                          </span>
                        </div>
                        {group.map((w) => (
                          <div key={w.worker_id} className="border-b border-[var(--chat-border)]">
                            <WorkerRow
                              worker={w}
                              expanded={selectedWorkerId === w.worker_id}
                              onClick={() => onSelectWorker(selectedWorkerId === w.worker_id ? null : w.worker_id)}
                            />
                          </div>
                        ))}
                      </div>
                    );
                  })
                ) : (
                  workers.map((w) => (
                    <div key={w.worker_id} className="border-b border-[var(--chat-border)]">
                      <WorkerRow
                        worker={w}
                        expanded={selectedWorkerId === w.worker_id}
                        onClick={() => onSelectWorker(selectedWorkerId === w.worker_id ? null : w.worker_id)}
                      />
                    </div>
                  ))
                )}
              </div>

              {/* Detail panel — outer div animates width; inner keeps content from reflowing */}
              <div
                style={{ transition: "width 400ms cubic-bezier(.32,1.4,.64,1)" }}
                className={cn(
                  "flex-shrink-0 h-full overflow-hidden border-l border-[var(--chat-border)]",
                  selectedWorkerId ? "w-[55%]" : "w-0",
                )}
              >
                <div className="w-[55vw] max-w-[300px] min-w-[220px] h-full">
                  {selectedWorker && (
                    <WorkerDetailContent
                      worker={selectedWorker}
                      onClose={() => onSelectWorker(null)}
                    />
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Decomposing spinner + optional previous-phase history */}
        {theaterPhase === "decomposing" && (
          <div className="flex flex-col h-full">
            <div className={cn(
              "flex flex-col items-center justify-center gap-3",
              previousPhaseWorkers.length > 0 ? "py-6 flex-shrink-0" : "h-full",
            )}>
              <div className="w-8 h-8 rounded-full border-2 border-[var(--chat-border)] border-t-[var(--chat-accent)] animate-spin" />
              <p className="text-xs text-[var(--chat-muted)]">Decomposing task&hellip;</p>
            </div>
            {previousPhaseWorkers.length > 0 && (
              <div className="flex-1 overflow-y-auto border-t border-[var(--chat-border)]">
                <div className="flex items-center gap-2 px-4 py-1.5 sticky top-0 bg-[var(--chat-surface)] border-b border-[var(--chat-border)]">
                  <div className="h-px flex-1 bg-[var(--chat-border)]" />
                  <span className="text-[7px] font-black tracking-[0.25em] text-[var(--chat-muted)] uppercase flex-shrink-0">Prior phase activity</span>
                  <div className="h-px flex-1 bg-[var(--chat-border)]" />
                </div>
                {previousPhaseWorkers.map((w) => (
                  <div key={w.worker_id} className="border-b border-[var(--chat-border)]">
                    <WorkerRow
                      worker={w}
                      expanded={selectedWorkerId === w.worker_id}
                      onClick={() => onSelectWorker(selectedWorkerId === w.worker_id ? null : w.worker_id)}
                    />
                  </div>
                ))}
              </div>
            )}
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
    dismissed, setDismissed, dequeueBadge, setTheaterPhase, setSelectedWorker,
  } = useSwarmStore();

  const handleCardDone = useCallback(() => {
    dequeueBadge();
  }, [dequeueBadge]);

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
          visible ? "translate-y-0" : "translate-y-full pointer-events-none",
        )}
      >
        {/* Drag handle */}
        <div className="flex-shrink-0 flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-[var(--chat-border)]" />
        </div>

        {/* Header */}
        <div className="flex items-center gap-2 px-5 py-3 border-b border-[var(--chat-border)] flex-shrink-0">
          <div className={cn(
            "w-1.5 h-1.5 rounded-full",
            theaterPhase === "complete" ? "bg-emerald-400" : "bg-emerald-400 animate-pulse",
          )} />
          <span className="text-xs font-semibold text-[var(--chat-text)] opacity-80 tracking-wide uppercase">
            {theaterPhase === "complete" ? "Swarm Complete" : "Swarm Active"}
          </span>
          <span className="text-[10px] text-[var(--chat-muted)] opacity-70 ml-1">
            {workers.length} pioneer{workers.length !== 1 ? "s" : ""}
          </span>
          <button
            onClick={() => setDismissed(true)}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] text-[var(--chat-muted)] hover:text-[var(--chat-text)] opacity-80 hover:bg-[var(--hover-tint)] transition-all"
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
    dismissed, popoutOpen, setDismissed, setPopoutOpen, setTheaterPhase, setSelectedWorker, dequeueBadge,
  } = useSwarmStore();

  const popupRef = useRef<Window | null>(null);

  const handleCardDone = useCallback(() => {
    dequeueBadge();
  }, [dequeueBadge]);

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
    const popup = window.open("/swarm", "memex-swarm-panel", "width=580,height=820,resizable=yes");
    if (popup) {
      popupRef.current = popup;
      setPopoutOpen(true);
      setDismissed(true);
    }
  }, [setPopoutOpen, setDismissed]);

  const visible = active && theaterPhase !== "idle" && !dismissed;

  return (
    /* Outer div — only manages width animation. Overflow-hidden clips content during slide */
    <div
      aria-hidden={!visible}
      style={{ transition: "width 500ms cubic-bezier(.32,1.4,.64,1)" }}
      className={cn(
        "flex-shrink-0 h-full overflow-hidden",
        visible ? "w-[min(540px,48vw)]" : "w-0",
      )}
    >
      {/* Inner content div — fixed width so text doesn't reflow during the animation */}
      <div className="w-[min(540px,48vw)] h-full flex flex-col bg-[var(--chat-bg)] border-l border-[var(--chat-border)]">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--chat-border)] flex-shrink-0">
        <div className={cn(
          "w-1.5 h-1.5 rounded-full",
          theaterPhase === "complete" ? "bg-emerald-400" : "bg-emerald-400 animate-pulse",
        )} />
        <span className="text-xs font-semibold text-[var(--chat-muted)] tracking-wide uppercase">
          {theaterPhase === "complete" ? "Swarm Complete" : "Swarm Active"}
        </span>
        <span className="ml-auto text-[10px] text-[var(--chat-muted)]">{workers.length} pioneer{workers.length !== 1 ? "s" : ""}</span>

        {/* Popout */}
        <button
          onClick={handlePopout}
          className="ml-2 p-1 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
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
          className="ml-1 p-1 rounded text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
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
          <div className="w-12 h-12 rounded-2xl bg-[var(--chat-soft)] border border-[var(--chat-border)] flex items-center justify-center">
            <svg className="w-5 h-5 text-[var(--chat-muted)]" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--chat-text)]">In external window</p>
            <p className="text-[11px] text-[var(--chat-muted)] mt-1">Swarm panel is open in a separate window</p>
          </div>
          <button
            onClick={() => {
              popupRef.current?.close();
              popupRef.current = null;
              setPopoutOpen(false);
              setDismissed(false);
            }}
            className="px-4 py-2 rounded-lg text-[11px] text-[var(--chat-muted)] border border-[var(--chat-border)] hover:bg-[var(--chat-soft)] transition-all"
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
      </div>{/* end inner content */}
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
