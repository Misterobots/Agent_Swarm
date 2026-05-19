"use client";

import { useEffect, useState, useRef } from "react";
import { fetchTrainingReport, fetchLiveTrainingMetrics, type TrainingReport } from "@/lib/api/training";
import type { LiveTrainingMetrics } from "@/types/training";
import {
  Clock,
  Database,
  Cpu,
  Sliders,
  TrendingDown,
  Rocket,
  GitCompare,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  XCircle,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Section, Stat, formatDuration, formatNumber } from "./report-helpers";
import { PipelineProgress } from "./pipeline-progress";

function formatEta(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function TrainingReportView({ runId }: { runId: number }) {
  const [report, setReport] = useState<TrainingReport | null>(null);
  const [live, setLive] = useState<LiveTrainingMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Initial report fetch
  useEffect(() => {
    fetchTrainingReport(runId).then((r) => {
      setReport(r);
      setLoading(false);
    });
  }, [runId]);

  // Live polling for running runs
  useEffect(() => {
    if (!report || (report.status !== "running" && report.status !== "pending")) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }

    const poll = () => {
      fetchLiveTrainingMetrics(runId).then(setLive);
      // Also refresh the report to get updated DB state
      fetchTrainingReport(runId).then((r) => {
        if (r) setReport(r);
      });
    };

    poll(); // Immediate first poll
    intervalRef.current = setInterval(poll, 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [runId, report?.status]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-[var(--chat-muted)] text-sm">
        <Loader2 size={14} className="animate-spin" />
        Generating report...
      </div>
    );
  }

  if (!report) {
    return (
      <p className="text-sm text-[var(--chat-muted)] py-4">
        Report unavailable for this run.
      </p>
    );
  }

  const t = report.timing;
  const d = report.dataset;
  const m = report.model;
  const r = report.results;
  const dep = report.deployment;
  const hp = report.hyperparameters;

  const isCompleted = report.status === "completed";
  const isFailed = report.status === "failed";

  const isRunning = !isCompleted && !isFailed;
  const liveData = report.live ?? live;

  return (
    <div className="space-y-5">
      {/* Status Banner */}
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg text-sm",
          isCompleted && "bg-emerald-500/5 border border-emerald-500/20",
          isFailed && "bg-red-500/5 border border-red-500/20",
          isRunning && "bg-amber-500/5 border border-amber-500/20"
        )}
      >
        {isCompleted ? (
          <CheckCircle2 size={14} className="text-emerald-400" />
        ) : isFailed ? (
          <XCircle size={14} className="text-red-400" />
        ) : (
          <Loader2 size={14} className="text-amber-400 animate-spin" />
        )}
        <span
          className={cn(
            "font-medium",
            isCompleted && "text-emerald-300",
            isFailed && "text-red-300",
            isRunning && "text-amber-300"
          )}
        >
          {isCompleted
            ? "Training Completed Successfully"
            : isFailed
            ? "Training Failed"
            : (liveData?.phase ?? report.phase)
            ? `In Progress: ${(liveData?.phase ?? report.phase ?? "").replace(/_/g, " ")}`
            : "Training In Progress"}
        </span>
        <span className="text-[var(--chat-muted)] ml-auto text-xs">
          Run #{report.run_id} &middot; {report.run_type}
        </span>
      </div>

      {/* Error */}
      {report.error && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={12} className="text-red-400" />
            <p className="text-xs font-medium text-red-400">Error</p>
          </div>
          <p className="text-xs text-red-300/80 font-mono whitespace-pre-wrap">
            {report.error}
          </p>
        </div>
      )}

      {/* Pipeline Progress */}
      <PipelineProgress
        runType={report.run_type}
        currentPhase={liveData?.phase ?? report.phase}
        status={report.status}
        phaseTimings={report.timing.phase_timings}
      />

      {/* Live Training Metrics (shown only for running runs) */}
      {isRunning && liveData && (
        <Section
          icon={<Activity size={14} className="text-amber-400 animate-pulse" />}
          title="Live Training"
        >
          {/* Step progress bar */}
          {liveData.total_steps != null && liveData.total_steps > 0 && (
            <div className="mb-3">
              <div className="flex justify-between text-xs text-[var(--chat-muted)] mb-1">
                <span>Step {liveData.current_step ?? 0} / {liveData.total_steps}</span>
                <span>
                  {liveData.current_epoch != null && liveData.total_epochs
                    ? `Epoch ${liveData.current_epoch.toFixed(2)} / ${liveData.total_epochs}`
                    : liveData.current_epoch != null
                    ? `Epoch ${liveData.current_epoch.toFixed(2)}`
                    : ""}
                </span>
              </div>
              <div className="h-2 rounded-full overflow-hidden bg-[var(--chat-surface)]">
                <div
                  className="h-full bg-amber-500 rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, ((liveData.current_step ?? 0) / liveData.total_steps) * 100)}%`,
                  }}
                />
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat
              label="Loss"
              value={liveData.loss != null ? liveData.loss.toFixed(4) : "—"}
            />
            <Stat
              label="Reward (mean)"
              value={liveData.reward_mean != null ? liveData.reward_mean.toFixed(4) : "—"}
              detail={liveData.reward_std != null ? `σ ${liveData.reward_std.toFixed(4)}` : undefined}
            />
            <Stat
              label="Step Time"
              value={liveData.step_time_sec != null ? `${liveData.step_time_sec.toFixed(1)}s` : "—"}
            />
            <Stat
              label="ETA"
              value={formatEta(liveData.eta_sec)}
              detail={
                liveData.budget_remaining_sec != null
                  ? `Budget: ${formatEta(liveData.budget_remaining_sec)} remaining`
                  : liveData.elapsed_sec != null
                  ? `Elapsed: ${formatEta(liveData.elapsed_sec)}`
                  : undefined
              }
            />
          </div>
          {liveData.entropy != null && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2">
              <Stat label="Entropy" value={liveData.entropy.toFixed(4)} />
              {liveData.learning_rate != null && (
                <Stat label="Learning Rate" value={liveData.learning_rate.toExponential(2)} />
              )}
            </div>
          )}
        </Section>
      )}

      {/* Timing */}
      <Section
        icon={<Clock size={14} className="text-[var(--chat-accent)]" />}
        title="Timing"
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat
            label="Total Wall Clock"
            value={t.total_wall_clock_sec ? formatDuration(t.total_wall_clock_sec) : "—"}
          />
          <Stat
            label="Active Training"
            value={t.active_training_sec ? formatDuration(t.active_training_sec) : "—"}
          />
          <Stat
            label="Overhead"
            value={t.overhead_sec ? formatDuration(t.overhead_sec) : "—"}
            detail={t.overhead_note}
          />
          <Stat
            label="Started"
            value={t.started_at ? new Date(t.started_at).toLocaleString() : "—"}
          />
        </div>
        {t.overhead_sec != null && t.total_wall_clock_sec != null && t.total_wall_clock_sec > 0 && (
          <div className="mt-2">
            <div className="flex gap-0.5 h-2 rounded-full overflow-hidden bg-[var(--chat-surface)]">
              <div
                className="bg-cyan-500 rounded-l-full"
                style={{
                  width: `${((t.active_training_sec ?? 0) / t.total_wall_clock_sec) * 100}%`,
                }}
                title="Active training"
              />
              <div
                className="bg-[var(--chat-surface)] rounded-r-full"
                style={{
                  width: `${(t.overhead_sec / t.total_wall_clock_sec) * 100}%`,
                }}
                title="Overhead (model load + dataset prep)"
              />
            </div>
            <div className="flex justify-between mt-1 text-[10px] text-[var(--chat-muted)]">
              <span>Training ({Math.round(((t.active_training_sec ?? 0) / t.total_wall_clock_sec) * 100)}%)</span>
              <span>Overhead ({Math.round((t.overhead_sec / t.total_wall_clock_sec) * 100)}%)</span>
            </div>
          </div>
        )}
        {t.phase_timings && (() => {
          const phases = Object.entries(t.phase_timings!).filter(([, v]) => v > 0);
          const total = phases.reduce((s, [, v]) => s + v, 0);
          if (!phases.length || total <= 0) return null;
          const colors: Record<string, string> = {
            synthetic_gen_sec: "bg-violet-500",
            security_scan_sec: "bg-red-400",
            dataset_download_sec: "bg-blue-400",
            model_loading_sec: "bg-amber-400",
            training_sec: "bg-cyan-500",
            saving_adapter_sec: "bg-emerald-400",
            exporting_traces_sec: "bg-pink-400",
          };
          return (
            <div className="mt-3">
              <div className="text-[10px] text-[var(--chat-muted)] mb-1">Phase Breakdown</div>
              <div className="flex gap-0.5 h-2 rounded-full overflow-hidden bg-[var(--chat-surface)]">
                {phases.map(([k, v], i) => (
                  <div
                    key={k}
                    className={`${colors[k] ?? "bg-gray-400"} ${i === 0 ? "rounded-l-full" : ""} ${i === phases.length - 1 ? "rounded-r-full" : ""}`}
                    style={{ width: `${(v / total) * 100}%` }}
                    title={`${k.replace(/_sec$/, "").replace(/_/g, " ")}: ${formatDuration(v)}`}
                  />
                ))}
              </div>
              <div className="flex flex-wrap gap-3 mt-1 text-[10px] text-[var(--chat-muted)]">
                {phases.map(([k, v]) => (
                  <span key={k} className="flex items-center gap-1">
                    <span className={`inline-block w-2 h-2 rounded-full ${colors[k] ?? "bg-gray-400"}`} />
                    {k.replace(/_sec$/, "").replace(/_/g, " ")} ({formatDuration(v)})
                  </span>
                ))}
              </div>
            </div>
          );
        })()}
      </Section>

      {/* Dataset */}
      <Section
        icon={<Database size={14} className="text-violet-500" />}
        title="Dataset"
      >
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Stat label="Total Samples" value={d.total_samples?.toLocaleString() ?? "—"} />
          <Stat label="Training Examples" value={d.training_examples?.toLocaleString() ?? "—"} />
          <Stat
            label="Source"
            value={d.path ? d.path.split("/").pop() ?? "—" : "—"}
          />
        </div>
      </Section>

      {/* Model */}
      <Section
        icon={<Cpu size={14} className="text-emerald-500" />}
        title="Model"
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Base Model" value={m.base_model ?? "—"} className="col-span-2" />
          <Stat
            label="Trainable Parameters"
            value={m.trainable_params ? formatNumber(m.trainable_params) : "—"}
            detail={m.trainable_pct ? `${m.trainable_pct}% of ${formatNumber(m.total_params ?? 0)} total` : undefined}
          />
          <Stat
            label="Total Parameters"
            value={m.total_params ? formatNumber(m.total_params) : "—"}
          />
        </div>
      </Section>

      {/* Hyperparameters */}
      <Section
        icon={<Sliders size={14} className="text-amber-500" />}
        title="Hyperparameters"
      >
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
          {Object.entries(hp).map(([k, v]) =>
            v != null ? (
              <Stat
                key={k}
                label={k.replace(/_/g, " ")}
                value={typeof v === "number" ? (v < 0.001 ? v.toExponential(1) : String(v)) : String(v)}
              />
            ) : null
          )}
        </div>
      </Section>

      {/* Results */}
      {(isCompleted || (isRunning && liveData)) && (
        <Section
          icon={<TrendingDown size={14} className="text-[var(--chat-accent)]" />}
          title={isRunning ? "Current Results" : "Results"}
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat
              label="Final Loss"
              value={
                (isRunning && liveData?.loss != null) ? liveData.loss.toFixed(4)
                : r.final_loss != null ? r.final_loss.toFixed(4) : "—"
              }
            />
            <Stat
              label="Samples/sec"
              value={r.train_samples_per_second ? r.train_samples_per_second.toFixed(2) : "—"}
            />
            <Stat
              label="Steps/sec"
              value={r.train_steps_per_second ? r.train_steps_per_second.toFixed(2) : "—"}
            />
            <Stat
              label="Adapter"
              value={r.adapter_path ? r.adapter_path.split("/").pop() ?? "—" : isRunning ? "In progress" : "—"}
              detail={r.adapter_path ?? undefined}
            />
          </div>
        </Section>
      )}

      {/* Deployment */}
      {dep.model_version && (
        <Section
          icon={<Rocket size={14} className="text-violet-500" />}
          title="Deployment"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Version" value={dep.model_version.version_tag} />
            <Stat
              label="Ollama Model"
              value={dep.model_version.ollama_model_name ?? "—"}
            />
            <Stat
              label="Status"
              value={
                <span
                  className={cn(
                    dep.model_version.status === "promoted" && "text-emerald-400",
                    dep.model_version.status === "ab_testing" && "text-amber-400",
                    dep.model_version.status === "candidate" && "text-[var(--chat-accent)]"
                  )}
                >
                  {dep.model_version.status}
                </span>
              }
            />
            <Stat
              label="Avg Score"
              value={dep.model_version.avg_score.toFixed(2)}
              detail={`${dep.model_version.total_invocations} invocations`}
            />
          </div>
        </Section>
      )}

      {/* A/B Test */}
      {dep.ab_test && (
        <Section
          icon={<GitCompare size={14} className="text-amber-500" />}
          title="A/B Test"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Candidate" value={dep.ab_test.candidate_model} />
            <Stat label="Baseline" value={dep.ab_test.base_model} />
            <Stat
              label="Status"
              value={
                <span
                  className={cn(
                    dep.ab_test.status === "completed" && "text-emerald-400",
                    dep.ab_test.status === "active" && "text-amber-400"
                  )}
                >
                  {dep.ab_test.status}
                  {dep.ab_test.winner && ` (${dep.ab_test.winner} won)`}
                </span>
              }
            />
            <Stat
              label="Results"
              value={`${dep.ab_test.result_count} samples`}
              detail={
                dep.ab_test.candidate_avg_score != null
                  ? `Candidate: ${dep.ab_test.candidate_avg_score.toFixed(3)} vs Base: ${dep.ab_test.base_avg_score?.toFixed(3) ?? "—"}`
                  : undefined
              }
            />
          </div>
        </Section>
      )}

      {/* No deployment yet */}
      {isCompleted && !dep.model_version && (
        <div className="border border-[var(--chat-border)] rounded-lg p-3 text-xs text-[var(--chat-muted)]">
          Adapter saved but not yet converted to GGUF or loaded into Ollama.
          Run the conversion step to deploy this model for A/B testing.
        </div>
      )}
    </div>
  );
}
