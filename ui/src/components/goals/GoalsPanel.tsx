"use client";

/**
 * GoalsPanel — Cowork-style task tracking panel.
 *
 * Rendered as a flex-sibling column inside chat-view (same pattern as
 * SwarmDesktopDrawer) so it integrates cleanly with the layout and never
 * overlaps the Swarm drawer or the chat content.
 *
 * Width animates between 320 px (open) and 0 (closed). A fixed toggle tab
 * on the panel's left edge stays reachable while the panel is open.
 */

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils/cn";
import { useGoalsStore } from "@/lib/stores/goals-store";
import { GoalStepRow } from "./GoalStepRow";
import type { PlanStatus } from "@/types/goals";

const PANEL_W = 320;

const EVIDENCE_TYPE_LABEL: Record<string, string> = {
  command_output: "Command",
  file_ref: "File",
  test_result: "Test",
  note: "Note",
};

export function GoalsPanel() {
  const activeGoal   = useGoalsStore((s) => s.activeGoal);
  const steps        = useGoalsStore((s) => s.steps);
  const evidence     = useGoalsStore((s) => s.evidence);
  const panelOpen    = useGoalsStore((s) => s.panelOpen);
  const setPanelOpen = useGoalsStore((s) => s.setPanelOpen);
  const updateStep   = useGoalsStore((s) => s.updateStep);
  const completeGoal = useGoalsStore((s) => s.completeGoal);
  const pauseGoal    = useGoalsStore((s) => s.pauseGoal);

  const [showEvidence, setShowEvidence] = useState(false);

  // Sweep animation fires once each time the panel opens
  const [panelSweeping, setPanelSweeping] = useState(false);
  const prevOpen = useRef(panelOpen);
  useEffect(() => {
    if (!prevOpen.current && panelOpen) setPanelSweeping(true);
    prevOpen.current = panelOpen;
  }, [panelOpen]);

  // Nothing to show — render nothing (no toggle tab either)
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
    /* Outer — manages width animation; overflow-hidden clips content during slide */
    <div
      style={{ transition: "width 300ms cubic-bezier(0.22,1,0.36,1)" }}
      className={cn(
        "flex-shrink-0 h-full overflow-hidden",
        panelOpen ? "w-[320px]" : "w-0",
      )}
    >
      {/* Inner — fixed width so text never reflows mid-animation */}
      <div
        className={cn(
          "h-full flex flex-col relative",
          "bg-[var(--chat-bg,#0f1021)] border-l border-[var(--border,rgba(255,255,255,0.1))]",
          "shadow-[-8px_0_32px_rgba(0,0,0,0.35)]",
        )}
        style={{ width: PANEL_W }}
      >
        {/* One-shot sweep on open */}
        {panelSweeping && (
          <div
            className="absolute inset-0 overflow-hidden pointer-events-none z-10"
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
              title="Collapse Goals panel"
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

          {/* Empty state — onboarding */}
          {steps.length === 0 && (
            <div className={cn(
              "glass-surface rounded-xl border border-[var(--border,rgba(255,255,255,0.08))]",
              "p-4 flex flex-col gap-3",
            )}>
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-[var(--accent)]/15 border border-[var(--accent)]/25 flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-[var(--accent)]" fill="none" viewBox="0 0 16 16">
                    <path d="M8 1l1.8 3.8L14 5.6l-3 2.9.7 4.1L8 10.5l-3.7 2.1.7-4.1L2 5.6l4.2-.8z"
                      stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
                  </svg>
                </div>
                <span className="text-[11px] font-semibold text-[var(--chat-fg,#e2e4f0)] tracking-wide">
                  Goals Mode
                </span>
              </div>

              <p className="text-[11px] text-[var(--chat-subtle)] leading-relaxed">
                Goals Mode turns a chat request into a tracked plan. When Memex breaks a task into steps, they appear here with{" "}
                <span className="text-[var(--chat-fg)]">pending → in progress → completed</span>{" "}
                status controls you can drive manually or let the agent advance automatically.
              </p>

              <div className="flex flex-col gap-1.5">
                <p className="text-[9px] font-bold uppercase tracking-[0.15em] text-[var(--chat-subtle)]">
                  Try saying
                </p>
                {[
                  "Plan out the implementation of X",
                  "Build Y step by step",
                  "Create a goal: research and summarise Z",
                ].map((example) => (
                  <div
                    key={example}
                    className="text-[10px] text-[var(--chat-subtle)] bg-[var(--border,rgba(255,255,255,0.04))] rounded-lg px-2.5 py-1.5 border border-[var(--border,rgba(255,255,255,0.06))] italic"
                  >
                    &ldquo;{example}&rdquo;
                  </div>
                ))}
              </div>

              <p className="text-[10px] text-[var(--chat-subtle)] opacity-70 leading-relaxed border-t border-[var(--border,rgba(255,255,255,0.06))] pt-3">
                Each step can collect <span className="not-italic font-medium text-[var(--chat-fg)]">evidence</span> — command output, file references, test results, or notes — so nothing gets lost between sessions.
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
              Complete ✓
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
    </div>
  );
}
