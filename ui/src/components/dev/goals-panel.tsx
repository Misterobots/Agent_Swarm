"use client";

import React, { useState, useEffect, useCallback } from "react";
import { RotateCw, ChevronDown, ChevronRight, Target } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { registerPanel } from "./dev-panels-registry";

// ── Types ──────────────────────────────────────────────────────────────────

type GoalStatus = "pending" | "in_progress" | "completed" | "paused";
type StepStatus = "pending" | "in_progress" | "completed";

interface PlanStep {
  id: string;
  description: string;
  status: StepStatus;
  order?: number;
}

interface Goal {
  id: string;
  objective: string;
  status: GoalStatus;
  plan_steps?: PlanStep[];
  created_at?: string;
}

interface GoalsResponse {
  goals: Goal[];
}

// ── Status chip ────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<GoalStatus, string> = {
  in_progress:
    "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)]",
  completed:
    "bg-[color:color-mix(in_srgb,#22c55e_15%,transparent)] text-[color:#4ade80]",
  pending: "bg-[color:color-mix(in_srgb,var(--chat-muted)_15%,transparent)] text-[var(--chat-muted)]",
  paused:
    "bg-[color:color-mix(in_srgb,#f59e0b_15%,transparent)] text-[color:#fbbf24]",
};

const STATUS_LABELS: Record<GoalStatus, string> = {
  in_progress: "In Progress",
  completed: "Completed",
  pending: "Pending",
  paused: "Paused",
};

function StatusChip({ status }: { status: GoalStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium tracking-wide shrink-0",
        STATUS_STYLES[status]
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

// ── Loading skeleton ───────────────────────────────────────────────────────

function GoalSkeleton() {
  return (
    <div className="space-y-2 p-3 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="rounded-md border border-[var(--chat-border)] bg-[var(--chat-surface)] p-3 space-y-2"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="h-3 bg-[var(--chat-border)] rounded w-2/3" />
            <div className="h-4 bg-[var(--chat-border)] rounded w-16" />
          </div>
          <div className="space-y-1.5 pl-2">
            <div className="h-2.5 bg-[var(--chat-border)] rounded w-full" />
            <div className="h-2.5 bg-[var(--chat-border)] rounded w-4/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Single goal row ────────────────────────────────────────────────────────

function GoalRow({
  goal,
  onStepToggle,
}: {
  goal: Goal;
  onStepToggle: (goalId: string, stepId: string, newStatus: StepStatus) => void;
}) {
  const [expanded, setExpanded] = useState(goal.status === "in_progress");
  const steps = goal.plan_steps ?? [];

  return (
    <div className="rounded-md border border-[var(--chat-border)] bg-[var(--chat-surface)] overflow-hidden">
      {/* Header row */}
      <button
        onClick={() => setExpanded((x) => !x)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-[var(--chat-panel)] transition-colors"
      >
        <span className="text-[var(--chat-muted)] shrink-0">
          {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </span>
        <span className="flex-1 text-[12px] font-medium text-[var(--chat-text)] leading-tight line-clamp-2">
          {goal.objective}
        </span>
        <StatusChip status={goal.status} />
      </button>

      {/* Steps */}
      {expanded && steps.length > 0 && (
        <div className="px-3 pb-2.5 space-y-1 border-t border-[var(--chat-border)]">
          {steps
            .slice()
            .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
            .map((step) => {
              const checked = step.status === "completed";
              return (
                <label
                  key={step.id}
                  className="flex items-start gap-2 py-1.5 cursor-pointer group"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() =>
                      onStepToggle(
                        goal.id,
                        step.id,
                        checked ? "pending" : "completed"
                      )
                    }
                    className="mt-0.5 shrink-0 accent-[var(--chat-accent)] cursor-pointer"
                  />
                  <span
                    className={cn(
                      "text-[12px] leading-snug transition-colors",
                      checked
                        ? "line-through text-[var(--chat-muted)]"
                        : "text-[var(--chat-text)] group-hover:text-[var(--chat-text)]"
                    )}
                  >
                    {step.description}
                  </span>
                </label>
              );
            })}
        </div>
      )}

      {expanded && steps.length === 0 && (
        <p className="px-3 pb-2.5 pt-1.5 text-[11px] text-[var(--chat-muted)] border-t border-[var(--chat-border)]">
          No steps defined.
        </p>
      )}
    </div>
  );
}

// ── Main panel component ───────────────────────────────────────────────────

export function GoalsPanel() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchGoals = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/backend/v1/goals?limit=20");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: GoalsResponse = await res.json();
      setGoals(data.goals ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load goals");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchGoals();
  }, [fetchGoals]);

  const handleStepToggle = useCallback(
    async (goalId: string, stepId: string, newStatus: StepStatus) => {
      // Optimistic update
      setGoals((prev) =>
        prev.map((g) =>
          g.id !== goalId
            ? g
            : {
                ...g,
                plan_steps: g.plan_steps?.map((s) =>
                  s.id === stepId ? { ...s, status: newStatus } : s
                ),
              }
        )
      );

      try {
        const res = await fetch(
          `/api/backend/v1/goals/${goalId}/step/${stepId}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: newStatus }),
          }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
      } catch {
        // Rollback on failure
        fetchGoals();
      }
    },
    [fetchGoals]
  );

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)] overflow-hidden">
      {/* Panel header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--chat-border)] shrink-0">
        <div className="flex items-center gap-2">
          <Target size={14} className="text-[var(--chat-accent)]" />
          <span className="text-[12px] font-semibold text-[var(--chat-text)]">Goals</span>
          {goals.length > 0 && (
            <span className="text-[10px] text-[var(--chat-muted)]">
              ({goals.length})
            </span>
          )}
        </div>
        <button
          onClick={() => fetchGoals(true)}
          disabled={refreshing}
          className="p-1 rounded hover:bg-[var(--chat-hover)] transition-colors"
          title="Refresh goals"
        >
          <RotateCw
            size={13}
            className={cn(
              "text-[var(--chat-muted)]",
              refreshing && "animate-spin"
            )}
          />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <GoalSkeleton />
        ) : error ? (
          <div className="p-4 text-center">
            <p className="text-[12px] text-red-400">{error}</p>
            <button
              onClick={() => fetchGoals()}
              className="mt-2 text-[11px] text-[var(--chat-accent)] hover:underline"
            >
              Retry
            </button>
          </div>
        ) : goals.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full px-6 py-10 text-center">
            <Target
              size={28}
              className="text-[var(--chat-muted)] opacity-40 mb-3"
            />
            <p className="text-[12px] text-[var(--chat-muted)] leading-relaxed">
              No goals yet — goals appear here when you run{" "}
              <code className="text-[var(--chat-text)] bg-[var(--chat-surface)] px-1 py-0.5 rounded text-[11px]">
                /workshop
              </code>{" "}
              or start a build.
            </p>
          </div>
        ) : (
          <div className="p-3 space-y-2">
            {goals.map((goal) => (
              <GoalRow
                key={goal.id}
                goal={goal}
                onStepToggle={handleStepToggle}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Self-registration ──────────────────────────────────────────────────────

registerPanel({
  id: "goals",
  title: "Goals",
  position: "right",
  icon: React.createElement(Target, { size: 14 }),
  component: GoalsPanel,
  toolbarOrder: 30,
  className: "w-[380px]",
});
