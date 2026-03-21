"use client";

import { useEffect, useState } from "react";
import { fetchTrainingStatus } from "@/lib/api/training";
import { Database, FlaskConical, GitCompare, Box } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { TrainingStatus } from "@/types/training";

export function TrainingStatusPanel() {
  const [status, setStatus] = useState<TrainingStatus | null>(null);

  useEffect(() => {
    fetchTrainingStatus().then(setStatus);
    const interval = setInterval(() => {
      fetchTrainingStatus().then(setStatus);
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  const lastRun = status.last_run;
  const totalData = status.dataset_size.exported + status.dataset_size.synthetic;

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium text-zinc-400">Training Pipeline</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Dataset Size */}
        <div className="border border-zinc-800 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <Database size={14} className="text-cyan-500" />
            <span className="text-xs text-zinc-500">Training Data</span>
          </div>
          <p className="text-lg font-semibold text-zinc-200">{totalData}</p>
          <p className="text-[10px] text-zinc-600">
            {status.dataset_size.exported} exported · {status.dataset_size.synthetic} synthetic
          </p>
        </div>

        {/* Last Run */}
        <div className="border border-zinc-800 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <FlaskConical size={14} className="text-violet-500" />
            <span className="text-xs text-zinc-500">Last Run</span>
          </div>
          {lastRun ? (
            <>
              <p className="text-sm font-medium text-zinc-200">{lastRun.run_type}</p>
              <p className="text-[10px] text-zinc-600">
                <span
                  className={cn(
                    lastRun.status === "completed" && "text-emerald-400",
                    lastRun.status === "failed" && "text-red-400",
                    lastRun.status === "running" && "text-amber-400",
                  )}
                >
                  {lastRun.status}
                </span>
                {" · "}
                {new Date(lastRun.started_at).toLocaleDateString()}
              </p>
            </>
          ) : (
            <p className="text-sm text-zinc-600">No runs yet</p>
          )}
        </div>

        {/* A/B Tests */}
        <div className="border border-zinc-800 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <GitCompare size={14} className="text-amber-500" />
            <span className="text-xs text-zinc-500">A/B Tests</span>
          </div>
          <p className="text-lg font-semibold text-zinc-200">{status.active_ab_tests}</p>
          <p className="text-[10px] text-zinc-600">active</p>
        </div>

        {/* Model Versions */}
        <div className="border border-zinc-800 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <Box size={14} className="text-emerald-500" />
            <span className="text-xs text-zinc-500">Model Versions</span>
          </div>
          <p className="text-lg font-semibold text-zinc-200">{status.model_versions.length}</p>
          <p className="text-[10px] text-zinc-600">
            {status.model_versions.filter((m) => m.status === "promoted").length} promoted
          </p>
        </div>
      </div>
    </div>
  );
}
