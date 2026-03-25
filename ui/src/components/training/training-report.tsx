"use client";

import { useEffect, useState } from "react";
import { fetchTrainingReport, type TrainingReport } from "@/lib/api/training";
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
} from "lucide-react";
import { cn } from "@/lib/utils/cn";

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
          {title}
        </h3>
      </div>
      {children}
    </div>
  );
}

function Stat({
  label,
  value,
  detail,
  className,
}: {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <p className="text-[10px] text-zinc-600 mb-0.5">{label}</p>
      <p className="text-sm font-mono text-zinc-200">{value}</p>
      {detail && <p className="text-[10px] text-zinc-600 mt-0.5">{detail}</p>}
    </div>
  );
}

export function TrainingReportView({ runId }: { runId: number }) {
  const [report, setReport] = useState<TrainingReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrainingReport(runId).then((r) => {
      setReport(r);
      setLoading(false);
    });
  }, [runId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-zinc-500 text-sm">
        <Loader2 size={14} className="animate-spin" />
        Generating report...
      </div>
    );
  }

  if (!report) {
    return (
      <p className="text-sm text-zinc-500 py-4">
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

  return (
    <div className="space-y-5">
      {/* Status Banner */}
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg text-sm",
          isCompleted && "bg-emerald-500/5 border border-emerald-500/20",
          isFailed && "bg-red-500/5 border border-red-500/20",
          !isCompleted && !isFailed && "bg-amber-500/5 border border-amber-500/20"
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
            !isCompleted && !isFailed && "text-amber-300"
          )}
        >
          {isCompleted
            ? "Training Completed Successfully"
            : isFailed
            ? "Training Failed"
            : "Training In Progress"}
        </span>
        <span className="text-zinc-500 ml-auto text-xs">
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

      {/* Timing */}
      <Section
        icon={<Clock size={14} className="text-cyan-500" />}
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
            <div className="flex gap-0.5 h-2 rounded-full overflow-hidden bg-zinc-800">
              <div
                className="bg-cyan-500 rounded-l-full"
                style={{
                  width: `${((t.active_training_sec ?? 0) / t.total_wall_clock_sec) * 100}%`,
                }}
                title="Active training"
              />
              <div
                className="bg-zinc-600 rounded-r-full"
                style={{
                  width: `${(t.overhead_sec / t.total_wall_clock_sec) * 100}%`,
                }}
                title="Overhead (model load + dataset prep)"
              />
            </div>
            <div className="flex justify-between mt-1 text-[10px] text-zinc-600">
              <span>Training ({Math.round(((t.active_training_sec ?? 0) / t.total_wall_clock_sec) * 100)}%)</span>
              <span>Overhead ({Math.round((t.overhead_sec / t.total_wall_clock_sec) * 100)}%)</span>
            </div>
          </div>
        )}
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
      {isCompleted && (
        <Section
          icon={<TrendingDown size={14} className="text-cyan-500" />}
          title="Results"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat
              label="Final Loss"
              value={r.final_loss != null ? r.final_loss.toFixed(4) : "—"}
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
              value={r.adapter_path ? r.adapter_path.split("/").pop() ?? "—" : "—"}
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
                    dep.model_version.status === "candidate" && "text-cyan-400"
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
        <div className="border border-zinc-800 rounded-lg p-3 text-xs text-zinc-500">
          Adapter saved but not yet converted to GGUF or loaded into Ollama.
          Run the conversion step to deploy this model for A/B testing.
        </div>
      )}
    </div>
  );
}
