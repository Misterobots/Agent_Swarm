"use client";

import { useEffect, useState } from "react";
import { fetchDeployReport, type DeployReport } from "@/lib/api/training";
import {
  GitCompare,
  BarChart3,
  Trophy,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Section, Stat, StatusBanner } from "./report-helpers";

export function DeployReportView({ runId }: { runId: number }) {
  const [report, setReport] = useState<DeployReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      const r = await fetchDeployReport(runId);
      if (!active) return;
      if (r) {
        setReport(r);
        setLoading(false);
      }
    };
    poll();
    // Auto-refresh while test is active
    const interval = setInterval(poll, 15000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [runId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-[var(--chat-muted)] text-sm">
        <Loader2 size={14} className="animate-spin" />
        Loading deploy report...
      </div>
    );
  }

  if (!report || report.status === "not_deployed") {
    return (
      <p className="text-sm text-[var(--chat-muted)] py-4">
        Model not yet deployed for A/B testing.
      </p>
    );
  }

  const test = report.test;
  const results = report.results;
  const isActive = test?.status === "active";
  const isConcluded = test?.status === "concluded";

  return (
    <div className="space-y-4 mt-3">
      {/* Status */}
      <StatusBanner
        status={isConcluded ? "completed" : isActive ? "running" : "pending"}
        label={
          isConcluded
            ? `A/B Test Concluded${test?.winner ? ` â€” ${test.winner} won` : ""}`
            : isActive
            ? "A/B Test Active"
            : "A/B Test Pending"
        }
        detail={test ? `Test #${test.id}` : undefined}
      />

      {/* Config */}
      {test && (
        <Section
          icon={<GitCompare size={14} className="text-amber-500" />}
          title="Test Configuration"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Template" value={test.template_id} />
            <Stat
              label="Candidate"
              value={test.candidate_model}
              className="truncate"
            />
            <Stat
              label="Baseline"
              value={test.base_model}
              className="truncate"
            />
            <Stat
              label="Traffic Split"
              value={
                test.traffic_split != null
                  ? `${(test.traffic_split * 100).toFixed(0)}% candidate`
                  : "â€”"
              }
            />
          </div>
        </Section>
      )}

      {/* Live Results */}
      {results && (
        <Section
          icon={<BarChart3 size={14} className="text-[var(--chat-accent)]" />}
          title="Results"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat
              label="Candidate Avg Score"
              value={
                results.candidate_avg_score != null
                  ? results.candidate_avg_score.toFixed(4)
                  : "â€”"
              }
              detail={`${results.n_candidate} samples`}
            />
            <Stat
              label="Baseline Avg Score"
              value={
                results.base_avg_score != null
                  ? results.base_avg_score.toFixed(4)
                  : "â€”"
              }
              detail={`${results.n_base} samples`}
            />
            <Stat
              label="Improvement"
              value={
                results.improvement_pct != null ? (
                  <span
                    className={cn(
                      results.improvement_pct > 0
                        ? "text-emerald-400"
                        : results.improvement_pct < 0
                        ? "text-red-400"
                        : "text-[var(--chat-muted)]"
                    )}
                  >
                    {results.improvement_pct > 0 ? "+" : ""}
                    {results.improvement_pct.toFixed(2)}%
                  </span>
                ) : (
                  "â€”"
                )
              }
            />
            <Stat
              label="P-Value"
              value={
                results.p_value != null ? (
                  <span
                    className={cn(
                      results.p_value < 0.05
                        ? "text-emerald-400"
                        : "text-[var(--chat-muted)]"
                    )}
                  >
                    {results.p_value.toFixed(4)}
                    {results.p_value < 0.05 && " (significant)"}
                  </span>
                ) : (
                  "â€”"
                )
              }
            />
          </div>

          {/* Progress bar */}
          {test && results.total_samples >= 0 && (
            <div className="mt-3">
              <div className="flex justify-between text-[10px] text-[var(--chat-muted)] mb-1">
                <span>
                  {results.total_samples} / {test.min_invocations} samples
                </span>
                <span>
                  {Math.min(
                    100,
                    Math.round(
                      (results.total_samples / test.min_invocations) * 100
                    )
                  )}
                  %
                </span>
              </div>
              <div className="h-2 rounded-full overflow-hidden bg-[var(--chat-surface)]">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    results.total_samples >= test.min_invocations
                      ? "bg-emerald-500"
                      : "bg-cyan-500"
                  )}
                  style={{
                    width: `${Math.min(
                      100,
                      (results.total_samples / test.min_invocations) * 100
                    )}%`,
                  }}
                />
              </div>
            </div>
          )}
        </Section>
      )}

      {/* Winner / Status */}
      {isConcluded && test?.winner && (
        <Section
          icon={<Trophy size={14} className="text-amber-400" />}
          title="Outcome"
        >
          <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3">
            <p className="text-sm text-emerald-300">
              <span className="font-semibold capitalize">{test.winner}</span>{" "}
              model won the A/B test.
              {test.winner === "candidate" && (
                <> The fine-tuned model outperformed the baseline.</>
              )}
              {test.winner === "base" && (
                <> The baseline model performed better than the candidate.</>
              )}
            </p>
          </div>
        </Section>
      )}

      {isActive && results && results.total_samples === 0 && (
        <div className="border border-[var(--chat-border)] rounded-lg p-3 text-xs text-[var(--chat-muted)]">
          <AlertTriangle size={12} className="inline mr-1 text-amber-400" />
          Collecting data... Results will appear as chat requests are routed
          through this template.
        </div>
      )}
    </div>
  );
}
