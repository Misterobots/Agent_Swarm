"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchTrainingRuns } from "@/lib/api/training";
import type { TrainingRun } from "@/types/training";
import { History, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export function TrainingRunHistory() {
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    const data = await fetchTrainingRuns(50);
    setRuns(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500">
        Loading run history...
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <History size={20} className="text-cyan-400" />
          <h1 className="text-lg font-semibold text-zinc-100">Run History</h1>
          <span className="text-xs text-zinc-600">{runs.length} runs</span>
        </div>
        <button
          onClick={refresh}
          className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      {runs.length === 0 ? (
        <div className="border border-zinc-800 rounded-lg p-8 text-center">
          <p className="text-zinc-500">No training runs recorded yet.</p>
          <p className="text-xs text-zinc-600 mt-1">
            Launch a run from the Launch tab to get started.
          </p>
        </div>
      ) : (
        <div className="border border-zinc-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-zinc-600 border-b border-zinc-800 bg-[#0a0a14]">
                <th className="text-left p-3 font-medium w-8"></th>
                <th className="text-left p-3 font-medium">ID</th>
                <th className="text-left p-3 font-medium">Type</th>
                <th className="text-left p-3 font-medium">Model</th>
                <th className="text-left p-3 font-medium">Status</th>
                <th className="text-right p-3 font-medium">Samples</th>
                <th className="text-right p-3 font-medium">Started</th>
                <th className="text-right p-3 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const expanded = expandedId === run.id;
                const duration =
                  run.completed_at && run.started_at
                    ? Math.round(
                        (new Date(run.completed_at).getTime() -
                          new Date(run.started_at).getTime()) /
                          1000
                      )
                    : null;

                return (
                  <Fragment key={run.id}>
                    <tr
                      className="border-b border-zinc-800/50 hover:bg-zinc-800/20 cursor-pointer"
                      onClick={() =>
                        setExpandedId(expanded ? null : run.id)
                      }
                    >
                      <td className="p-3 text-zinc-600">
                        {expanded ? (
                          <ChevronUp size={14} />
                        ) : (
                          <ChevronDown size={14} />
                        )}
                      </td>
                      <td className="p-3 text-zinc-400 font-mono text-xs">
                        #{run.id}
                      </td>
                      <td className="p-3 text-zinc-300">{run.run_type}</td>
                      <td className="p-3 text-zinc-400 truncate max-w-[180px]">
                        {run.target_model ?? "—"}
                      </td>
                      <td className="p-3">
                        <span
                          className={cn(
                            "text-xs px-2 py-0.5 rounded-full",
                            run.status === "completed" &&
                              "bg-emerald-500/10 text-emerald-400",
                            run.status === "failed" &&
                              "bg-red-500/10 text-red-400",
                            run.status === "running" &&
                              "bg-amber-500/10 text-amber-400",
                            run.status === "pending" &&
                              "bg-zinc-500/10 text-zinc-400"
                          )}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="p-3 text-right text-zinc-400">
                        {run.dataset_size ?? "—"}
                      </td>
                      <td className="p-3 text-right text-zinc-500 text-xs">
                        {new Date(run.started_at).toLocaleString()}
                      </td>
                      <td className="p-3 text-right text-zinc-400 text-xs">
                        {duration != null ? formatDuration(duration) : "—"}
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="bg-zinc-900/50">
                        <td colSpan={8} className="p-4">
                          <TrainingReportView runId={run.id} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

import { Fragment } from "react";
import { TrainingReportView } from "./training-report";

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}
