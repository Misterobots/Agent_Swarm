"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchTrainingStatus } from "@/lib/api/training";
import type { TrainingStatus } from "@/types/training";
import {
  Database,
  FlaskConical,
  GitCompare,
  Box,
  Activity,
  Clock,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";

export function TrainingOverview() {
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const data = await fetchTrainingStatus();
    setStatus(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 15000);
    return () => clearInterval(interval);
  }, [refresh]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500">
        Loading training status...
      </div>
    );
  }

  const lastRun = status?.last_run;
  const totalData =
    (status?.dataset_size.exported ?? 0) +
    (status?.dataset_size.synthetic ?? 0);
  const activeRun = status?.active_run;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FlaskConical size={20} className="text-violet-400" />
          <h1 className="text-lg font-semibold text-zinc-100">
            Training Pipeline
          </h1>
        </div>
        <button
          onClick={refresh}
          className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      {/* Active Training Banner */}
      {activeRun && (
        <div className="border border-amber-500/30 bg-amber-500/5 rounded-lg p-4 flex items-center gap-3">
          <Activity size={16} className="text-amber-400 animate-pulse" />
          <div>
            <p className="text-sm font-medium text-amber-300">
              Training in progress
            </p>
            <p className="text-xs text-zinc-500">
              Started{" "}
              {activeRun.started_at
                ? new Date(activeRun.started_at).toLocaleTimeString()
                : "just now"}
              {activeRun.run_id && ` (Run #${activeRun.run_id})`}
            </p>
          </div>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          icon={<Database size={16} className="text-cyan-500" />}
          label="Training Data"
          value={totalData.toLocaleString()}
          detail={`${status?.dataset_size.exported ?? 0} exported · ${status?.dataset_size.synthetic ?? 0} synthetic`}
        />
        <MetricCard
          icon={<FlaskConical size={16} className="text-violet-500" />}
          label="Last Run"
          value={lastRun?.run_type ?? "None"}
          detail={
            lastRun ? (
              <span>
                <span
                  className={cn(
                    lastRun.status === "completed" && "text-emerald-400",
                    lastRun.status === "failed" && "text-red-400",
                    lastRun.status === "running" && "text-amber-400"
                  )}
                >
                  {lastRun.status}
                </span>
                {" · "}
                {new Date(lastRun.started_at).toLocaleDateString()}
              </span>
            ) : (
              "No runs yet"
            )
          }
        />
        <MetricCard
          icon={<GitCompare size={16} className="text-amber-500" />}
          label="A/B Tests"
          value={String(status?.active_ab_tests ?? 0)}
          detail="active"
        />
        <MetricCard
          icon={<Box size={16} className="text-emerald-500" />}
          label="Model Versions"
          value={String(status?.model_versions.length ?? 0)}
          detail={`${status?.model_versions.filter((m) => m.status === "promoted").length ?? 0} promoted`}
        />
      </div>

      {/* Last Run Details */}
      {lastRun && (
        <div className="border border-zinc-800 rounded-lg p-4 space-y-3">
          <h2 className="text-sm font-medium text-zinc-400">
            Last Run Details
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-xs text-zinc-600">Model</p>
              <p className="text-zinc-300 truncate">
                {lastRun.target_model ?? "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-zinc-600">Dataset Size</p>
              <p className="text-zinc-300">
                {lastRun.dataset_size ?? "—"} samples
              </p>
            </div>
            <div>
              <p className="text-xs text-zinc-600">Loss</p>
              <p className="text-zinc-300">
                {lastRun.metrics.train_loss != null
                  ? Number(lastRun.metrics.train_loss).toFixed(4)
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-zinc-600">Runtime</p>
              <p className="text-zinc-300">
                {lastRun.metrics.train_runtime != null
                  ? `${Number(lastRun.metrics.train_runtime).toFixed(0)}s`
                  : "—"}
              </p>
            </div>
          </div>
          {lastRun.error_message && (
            <div className="bg-red-500/5 border border-red-500/20 rounded p-2">
              <p className="text-xs text-red-400">{lastRun.error_message}</p>
            </div>
          )}
        </div>
      )}

      {/* Model Versions Table */}
      {(status?.model_versions.length ?? 0) > 0 && (
        <div className="border border-zinc-800 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-zinc-800">
            <h2 className="text-sm font-medium text-zinc-400">
              Model Versions
            </h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-zinc-600 border-b border-zinc-800">
                <th className="text-left p-3 font-medium">Version</th>
                <th className="text-left p-3 font-medium">Base Model</th>
                <th className="text-left p-3 font-medium">Status</th>
                <th className="text-right p-3 font-medium">Score</th>
                <th className="text-right p-3 font-medium">Invocations</th>
              </tr>
            </thead>
            <tbody>
              {status!.model_versions.map((mv) => (
                <tr
                  key={mv.id}
                  className="border-b border-zinc-800/50 hover:bg-zinc-800/20"
                >
                  <td className="p-3 text-zinc-300 font-mono text-xs">
                    {mv.version_tag}
                  </td>
                  <td className="p-3 text-zinc-400 truncate max-w-[200px]">
                    {mv.base_model}
                  </td>
                  <td className="p-3">
                    <span
                      className={cn(
                        "text-xs px-2 py-0.5 rounded-full",
                        mv.status === "promoted" &&
                          "bg-emerald-500/10 text-emerald-400",
                        mv.status === "ab_testing" &&
                          "bg-amber-500/10 text-amber-400",
                        mv.status === "candidate" &&
                          "bg-cyan-500/10 text-cyan-400",
                        mv.status === "retired" &&
                          "bg-zinc-500/10 text-zinc-500"
                      )}
                    >
                      {mv.status}
                    </span>
                  </td>
                  <td className="p-3 text-right text-zinc-300">
                    {mv.avg_score.toFixed(2)}
                  </td>
                  <td className="p-3 text-right text-zinc-400">
                    {mv.total_invocations.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  detail,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: React.ReactNode;
}) {
  return (
    <div className="border border-zinc-800 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs text-zinc-500">{label}</span>
      </div>
      <p className="text-xl font-semibold text-zinc-200">{value}</p>
      <p className="text-xs text-zinc-600 mt-1">{detail}</p>
    </div>
  );
}
