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
  const totalData =
    status.dataset_size.exported +
    status.dataset_size.synthetic +
    (status.dataset_size.curated ?? 0);
  const activeRun = status.active_run;

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium text-[var(--chat-muted)]">Training Pipeline</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Dataset Size */}
        <div className="border border-[var(--chat-border)] rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <Database size={14} className="text-[var(--chat-accent)]" />
            <span className="text-xs text-[var(--chat-muted)]">Training Data</span>
          </div>
          <p className="text-lg font-semibold text-[var(--chat-text)]">{totalData}</p>
          <p className="text-[10px] text-[var(--chat-muted)]">
            {status.dataset_size.exported} exported · {status.dataset_size.synthetic} synthetic · {status.dataset_size.curated ?? 0} curated
          </p>
        </div>

        {/* Last Run */}
        <div className="border border-[var(--chat-border)] rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <FlaskConical size={14} className="text-violet-500" />
            <span className="text-xs text-[var(--chat-muted)]">Last Run</span>
          </div>
          {lastRun ? (
            <>
              <p className="text-sm font-medium text-[var(--chat-text)]">{lastRun.run_type}</p>
              <p className="text-[10px] text-[var(--chat-muted)]">
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
            <p className="text-sm text-[var(--chat-muted)]">No runs yet</p>
          )}
        </div>

        {/* A/B Tests */}
        <div className="border border-[var(--chat-border)] rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <GitCompare size={14} className="text-amber-500" />
            <span className="text-xs text-[var(--chat-muted)]">A/B Tests</span>
          </div>
          <p className="text-lg font-semibold text-[var(--chat-text)]">{status.active_ab_tests}</p>
          <p className="text-[10px] text-[var(--chat-muted)]">active</p>
        </div>

        {/* Model Versions */}
        <div className="border border-[var(--chat-border)] rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <Box size={14} className="text-emerald-500" />
            <span className="text-xs text-[var(--chat-muted)]">Model Versions</span>
          </div>
          <p className="text-lg font-semibold text-[var(--chat-text)]">{status.model_versions.length}</p>
          <p className="text-[10px] text-[var(--chat-muted)]">
            {status.model_versions.filter((m) => m.status === "promoted").length} promoted
          </p>
        </div>
      </div>

      {activeRun && (
        <div className="border border-amber-500/20 bg-amber-500/5 rounded-lg px-3 py-2">
          <p className="text-[11px] text-amber-300 font-medium">Training active</p>
          <p className="text-[10px] text-[var(--chat-muted)]">
            {activeRun.run_id ? `Run #${activeRun.run_id}` : "Run pending"}
            {activeRun.run_type ? ` · ${activeRun.run_type}` : ""}
            {activeRun.started_at ? ` · started ${new Date(activeRun.started_at).toLocaleTimeString()}` : ""}
          </p>
        </div>
      )}
    </div>
  );
}
