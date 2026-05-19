"use client";

import { cn } from "@/lib/utils/cn";
import type { GoalPlanStep, PlanStatus } from "@/types/goals";

interface Props {
  step: GoalPlanStep;
  onSetStatus?: (stepId: string, status: PlanStatus) => void;
  readonly?: boolean;
}

export function GoalStepRow({ step, onSetStatus, readonly }: Props) {
  const { status } = step;

  return (
    <div
      className={cn(
        "flex items-start gap-3 py-2 px-1 rounded-lg transition-colors",
        status === "in_progress" && "bg-[var(--surface-elevated,rgba(255,255,255,0.04))]",
      )}
    >
      {/* Status indicator */}
      <div className="mt-0.5 flex-shrink-0">
        {status === "completed" && (
          <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center">
            <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 12 12">
              <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        )}
        {status === "in_progress" && (
          <div className="w-5 h-5 flex items-center justify-center">
            <svg
              className="w-4 h-4 text-[var(--accent,#7c6af7)] animate-spin"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path
                className="opacity-80"
                d="M12 2a10 10 0 0 1 10 10"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              />
            </svg>
          </div>
        )}
        {status === "pending" && (
          <div className="w-5 h-5 rounded-full border border-[var(--border,rgba(255,255,255,0.12))] flex-shrink-0" />
        )}
      </div>

      {/* Step text */}
      <span
        className={cn(
          "text-sm leading-snug flex-1",
          status === "completed" && "line-through text-[var(--chat-subtle,#8b8fa8)] opacity-60",
          status === "in_progress" && "text-[var(--chat-fg,#e2e4f0)] font-medium",
          status === "pending" && "text-[var(--chat-subtle,#8b8fa8)]",
        )}
      >
        {step.step}
      </span>

      {/* Quick status toggle (not shown in readonly mode) */}
      {!readonly && onSetStatus && (
        <div className="flex-shrink-0">
          {status === "pending" && (
            <button
              onClick={() => onSetStatus(step.id, "in_progress")}
              className="text-[10px] text-[var(--chat-subtle)] hover:text-[var(--accent)] transition-colors px-1.5 py-0.5 rounded border border-transparent hover:border-[var(--border)] whitespace-nowrap"
            >
              Start
            </button>
          )}
          {status === "in_progress" && (
            <button
              onClick={() => onSetStatus(step.id, "completed")}
              className="text-[10px] text-[var(--chat-subtle)] hover:text-green-400 transition-colors px-1.5 py-0.5 rounded border border-transparent hover:border-green-500/30 whitespace-nowrap"
            >
              Done
            </button>
          )}
        </div>
      )}
    </div>
  );
}
