"use client";

/**
 * GoalsPanel â€” Cowork-style task tracking panel.
 *
 * Design language:
 *  - Glassomorphic: frosted-glass surface with backdrop-filter blur.
 *  - Sweep animation fires once when the panel opens (glass-panel-enter)
 *    and when individual steps change state (handled in GoalStepRow).
 *  - Slides in as a right-side drawer inside the chat layout.
 *  - Auto-opens when a goal is created for the thread.
 */

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils/cn";
import { useGoalsStore } from "@/lib/stores/goals-store";
import { GoalStepRow } from "./GoalStepRow";
import type { PlanStatus } from "@/types/goals";

const EVIDENCE_TYPE_LABEL: Record<string, string> = {
  command_output: "Command",
  file_ref: "File",
  test_result: "Test",
  note: "Note",
};

export function GoalsPanel() {
  const activeGoal  = useGoalsStore((s) => s.activeGoal);
  const steps       = useGoalsStore((s) => s.steps);
  const evidence    = useGoalsStore((s) => s.evidence);
  const panelOpen   = useGoalsStore((s) => s.panelOpen);
  const setPanelOpen = useGoalsStore((s) => s.setPanelOpen);
  const updateStep  = useGoalsStore((s) => s.updateStep);
  const completeGoal = useGoalsStore((s) => s.completeGoal);
  const pauseGoal   = useGoalsStore((s) => s.pauseGoal);

  const [showEvidence, setShowEvidence] = useState(false);

  // Sweep fires once each time the panel opens
  const [panelSweeping, setPanelSweeping] = useState(false);
  const prevOpen = useRef(panelOpen);
  useEffect(() => {
    if (!prevOpen.current && panelOpen) {
      setPanelSweeping(true);
    }
    prevOpen.current = panelOpen;
  }, [panelOpen]);

  if (!activeGoal) return null;

  const total       = steps.length;
  const done        = steps.filter((s) => s.status === "completed").length;
  const progressPct = total > 0 ? Math.round((done / total) * 100) : 0;
  const isComplete  = activeGoal.status === "complete";
  const isPaused    = activeGoal.status === "paused";

  const handleStepStatus = async (stepId: string, status: PlanStatus) => {
    await updateStep(activeGoal.id, stepId, status);
  };

  const statusColor = isComplete
    ? "bg-green-500/15 border-green-500/25 text-green-400"
    : isPaused
    ? "bg-amber-500/15 border-amber-500/25 text-amber-400"
    : "bg-[var(--accent)]/10 border-[var(--accent)]/20 text-[var(--accent)]";

  return (
    <>
      {/* Toggle tab */}
      <button
        onClick={() => setPanelOpen(!panelOpen)}
        className={cn(
          "fixed right-0 top-1/2 -translate-y-1/2 z-30",
          "flex flex-col items-center gap-1 px-1 py-3 rounded-l-lg",
          "border border-r-0 border-[var(--border,rgba(255,255,255,0.1))]",
          "bg-[var(--surface,#1a1b2e)] shadow-lg transition-all duration-300",
          "hover:bg-[var(--surface-elevated)] text-[var(--chat-subtle)]",
          panelOpen && "right-[320px]",
        )}
        title={panelOpen ? "Hide Goals" : "Show Goals"}
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 16 16">
          <rect x="2" y="3" width="12" height="2" rx="1" fill="currentColor" opacity="0.6" />
          <rect x="2" y="7" width="8"  height="2" rx="1" fill="currentColor" />
          <rect x="2" y="11" width="10" height="2" rx="1" fill="currentColor" opacity="0.6" />
        </svg>
        <span className="text-[9px] font-semibold uppercase tracking-widest [writing-mode:vertical-rl] rotate-180">
          Goals
        </span>
        {!panelOpen && steps.some((s) => s.status === "in_progress") && (
          <div className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" />
        )}
      </button>

      {/* Panel â€” glassomorphic surface */}
      <div
        className={cn(
          "fixed right-0 top-0 bottom-0 z-20 w-[320px]",
          "flex flex-col",
          // Glass surface: frosted backdrop + subtle border
          "glass-surface",
          "border-l border-[var(--border,rgba(255,255,255,0.1))] shadow-2xl",
          // Slide transition
          "transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
          panelOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* One-shot sweep across the full panel on open */}
        {panelSweeping && (
          <div
            className="absolute inset-0 overflow-hidden pointer-events-none z-10 rounded-none"
            onAnimationEnd={() => setPanelSweeping(false)}
          >
            <div className="glass-sweep-shimmer" style={{ width: "70%" }} />
          </div>
        )}

        {/* Header */}
        <div className={cn(
          "relative overflow-hidden flex items-center justify-between px-4 py-3",
          "border-b border-[var(--border,rgba(255,255,255,0.08))]",
          panelOpen && "glass-panel-enter",
        )}>
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-[var(--accent)]" fill="none" viewBox="0 0 16 16">
              <path
                d="M8 1l1.8 3.8L14 5.6l-3 2.9.7 4.1L8 10.5l-3.7 2.1.7-4.1L2 5.6l4.2-.8z"
                stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"
              />
            </svg>
            <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">
              Active Goal
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={cn(
              "text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border",
              statusColor,
            )}>
              {activeGoal.status}
            </span>
            <button
              onClick={() => setPanelOpen(false)}
              className="p-1 rounded hover:bg-[var(--surface-elevated)] text-[var(--chat-subtle)] transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14">
                <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-4">

          {/* Objective */}
          <div>
            <p className="text-sm font-medium text-[var(--chat-fg,#e2e4f0)] leading-snug">
              {activeGoal.objective}
            </p>
          </div>

          {/* Progress bar */}
          {total > 0 && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] text-[var(--chat-subtle)] uppercase tracking-wide font-semibold">
                  Progress
                </span>
                <span className="text-[10px] text-[var(--chat-subtle)]">
                  {done}/{total} steps
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-[var(--border,rgba(255,255,255,0.08))] overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500 ease-out",
                    isComplete ? "bg-green-500" : "bg-[var(--accent,#7c6af7)]",
                  )}
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>
          )}

          {/* Plan steps */}
          {steps.length > 0 && (
            <div>
              <div className="text-[10px] text-[var(--chat-subtle)] uppercase tracking-[0.12em] font-semibold mb-2">
                Plan
              </div>
              <div className="flex flex-col">
                {[...steps]
                  .sort((a, b) => a.ord - b.ord)
                  .map((step, idx) => (
                    <div
                      key={step.id}
                      className="glass-row-enter"
                      style={{ animationDelay: `${idx * 40}ms` }}
                    >
                      <GoalStepRow
                        step={step}
                        onSetStatus={!isComplete ? handleStepStatus : undefined}
                        readonly={isComplete || isPaused}
                      />
                    </div>
                  ))}
              </div>
            </div>
          )}

          {steps.length === 0 && (
            <div className="py-4 text-center">
              <p className="text-[var(--chat-subtle)] text-xs">
                No plan steps yet. The agent will add them as work progresses.
              </p>
            </div>
          )}

          {/* Evidence (collapsible) */}
          {evidence.length > 0 && (
            <div>
              <button
                onClick={() => setShowEvidence((v) => !v)}
                className="flex items-center gap-1.5 text-[10px] text-[var(--chat-subtle)] uppercase
                           tracking-[0.12em] font-semibold hover:text-[var(--chat-fg)] transition-colors w-full"
              >
                <svg
                  className={cn("w-3 h-3 transition-transform", showEvidence && "rotate-90")}
                  fill="none" viewBox="0 0 12 12"
                >
                  <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Evidence ({evidence.length})
              </button>

              {showEvidence && (
                <div className="mt-2 flex flex-col gap-1.5">
                  {evidence.map((ev) => (
                    <div
                      key={ev.id}
                      className="relative overflow-hidden flex items-start gap-2 p-2 rounded-lg
                                 glass-surface border-[var(--border,rgba(255,255,255,0.06))]
                                 glass-row-enter"
                    >
                      <span className="text-[9px] font-bold uppercase tracking-wide text-[var(--chat-subtle)]
                                       bg-[var(--border,rgba(255,255,255,0.08))] rounded px-1.5 py-0.5 flex-shrink-0 mt-0.5">
                        {EVIDENCE_TYPE_LABEL[ev.evidenceType] ?? ev.evidenceType}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[10px] text-[var(--chat-subtle)] truncate">{ev.requirement}</p>
                        <p className="text-xs text-[var(--chat-fg)] break-all leading-snug">{ev.evidenceRef}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer actions */}
        {!isComplete && (
          <div className="px-4 py-3 border-t border-[var(--border,rgba(255,255,255,0.08))] flex gap-2">
            {!isPaused && (
              <button
                onClick={() => pauseGoal(activeGoal.id)}
                className="flex-1 py-1.5 text-xs rounded-lg border border-[var(--border)]
                           text-[var(--chat-subtle)] hover:text-[var(--chat-fg)]
                           hover:border-[var(--chat-subtle)] transition-colors"
              >
                Pause
              </button>
            )}
            {isPaused && (
              <button className="flex-1 py-1.5 text-xs rounded-lg border border-amber-500/30
                                 text-amber-400 hover:bg-amber-500/10 transition-colors">
                Paused
              </button>
            )}
            <button
              onClick={() => completeGoal(activeGoal.id)}
              className="flex-1 py-1.5 text-xs rounded-lg bg-green-500/15 border border-green-500/25
                         text-green-400 hover:bg-green-500/25 transition-colors font-medium"
            >
              Complete âœ“
            </button>
          </div>
        )}

        {isComplete && (
          <div className="px-4 py-3 border-t border-[var(--border,rgba(255,255,255,0.08))]">
            <div className="flex items-center justify-center gap-2 text-green-400 text-xs font-medium">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16">
                <path d="M3 8l4 4 6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Goal completed
            </div>
          </div>
        )}
      </div>
    </>
  );
}