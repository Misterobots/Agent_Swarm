"use client";

import { cn } from "@/lib/utils/cn";
import { CheckCircle2, Loader2, Circle } from "lucide-react";

/** Ordered pipeline stages for different run types */
const PIPELINE_STAGES: Record<string, string[]> = {
  synthetic: [
    "synthetic_generation",
    "security_scan",
    "model_loading",
    "training",
    "saving_adapter",
  ],
  curated: [
    "dataset_download",
    "security_scan",
    "model_loading",
    "training",
    "saving_adapter",
  ],
  full_pipeline: [
    "exporting_traces",
    "model_loading",
    "training",
    "saving_adapter",
  ],
  training: ["model_loading", "training", "saving_adapter"],
  export: ["exporting_traces"],
};

const STAGE_LABELS: Record<string, string> = {
  synthetic_generation: "Synthetic Gen",
  security_scan: "Security Scan",
  dataset_download: "Dataset Download",
  model_loading: "Model Loading",
  training: "Training",
  saving_adapter: "Saving Adapter",
  exporting_traces: "Exporting Traces",
  completed: "Completed",
  failed: "Failed",
};

interface PipelineProgressProps {
  runType: string;
  currentPhase: string | null | undefined;
  status: string;
  phaseTimings?: Record<string, number> | null;
}

export function PipelineProgress({
  runType,
  currentPhase,
  status,
  phaseTimings,
}: PipelineProgressProps) {
  const stages = PIPELINE_STAGES[runType] ?? PIPELINE_STAGES.training;
  const isCompleted = status === "completed";
  const isFailed = status === "failed";

  // Find current stage index
  const currentIndex = currentPhase
    ? stages.indexOf(currentPhase)
    : isCompleted
    ? stages.length
    : -1;

  return (
    <div className="flex items-center gap-1 py-2 overflow-x-auto">
      {stages.map((stage, idx) => {
        const isDone = isCompleted || idx < currentIndex;
        const isActive = !isCompleted && !isFailed && idx === currentIndex;
        const isPending = !isDone && !isActive;
        const timing = phaseTimings?.[stage + "_sec"];

        return (
          <div key={stage} className="flex items-center gap-1">
            {idx > 0 && (
              <div
                className={cn(
                  "w-4 h-px",
                  isDone ? "bg-emerald-500" : isActive ? "bg-amber-500" : "bg-[var(--chat-border)]"
                )}
              />
            )}
            <div
              className={cn(
                "flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] whitespace-nowrap border",
                isDone && "bg-emerald-500/5 border-emerald-500/20 text-emerald-400",
                isActive && "bg-amber-500/5 border-amber-500/20 text-amber-400",
                isPending && "bg-[var(--chat-surface)] border-[var(--chat-border)] text-[var(--chat-muted)]",
                isFailed && isActive && "bg-red-500/5 border-red-500/20 text-red-400"
              )}
              title={timing ? `${Math.round(timing)}s` : undefined}
            >
              {isDone ? (
                <CheckCircle2 size={10} />
              ) : isActive ? (
                <Loader2 size={10} className="animate-spin" />
              ) : (
                <Circle size={10} />
              )}
              <span>{STAGE_LABELS[stage] ?? stage.replace(/_/g, " ")}</span>
              {timing != null && (
                <span className="text-[var(--chat-muted)]">
                  {timing < 60 ? `${Math.round(timing)}s` : `${Math.round(timing / 60)}m`}
                </span>
              )}
            </div>
          </div>
        );
      })}

      {/* Terminal state */}
      {(isCompleted || isFailed) && (
        <div className="flex items-center gap-1">
          <div
            className={cn(
              "w-4 h-px",
              isCompleted ? "bg-emerald-500" : "bg-red-500"
            )}
          />
          <div
            className={cn(
              "flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] border",
              isCompleted && "bg-emerald-500/5 border-emerald-500/20 text-emerald-400",
              isFailed && "bg-red-500/5 border-red-500/20 text-red-400"
            )}
          >
            {isCompleted ? <CheckCircle2 size={10} /> : <Circle size={10} />}
            <span>{isCompleted ? "Done" : "Failed"}</span>
          </div>
        </div>
      )}
    </div>
  );
}
