"use client";

import { useState, useCallback } from "react";
import { useArtStore, JOINT_TYPES, type JointName } from "@/lib/stores/art-store";
import { segmentWithJoints } from "@/lib/api/art";
import { Crosshair, Check, X, Scissors, Loader2, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const JOINT_LABELS: Record<string, string> = {
  neck: "Neck",
  left_shoulder: "L Shoulder",
  right_shoulder: "R Shoulder",
  left_elbow: "L Elbow",
  right_elbow: "R Elbow",
  waist: "Waist",
  left_hip: "L Hip",
  right_hip: "R Hip",
  left_knee: "L Knee",
  right_knee: "R Knee",
};

const JOINT_COLORS: Record<string, string> = {
  neck: "bg-amber-500",
  left_shoulder: "bg-blue-500", right_shoulder: "bg-blue-500",
  left_elbow: "bg-violet-500", right_elbow: "bg-violet-500",
  waist: "bg-red-500",
  left_hip: "bg-emerald-500", right_hip: "bg-emerald-500",
  left_knee: "bg-pink-500", right_knee: "bg-pink-500",
};

interface JointEditorProps {
  meshPath: string;
  onSegmentComplete?: (result: string) => void;
  onBack?: () => void;
}

export function JointEditor({ meshPath, onSegmentComplete, onBack }: JointEditorProps) {
  const {
    activeJoint, setActiveJoint,
    placedJoints, removeJoint, clearJoints,
    actionFigureSettings,
  } = useArtStore();

  const [segmenting, setSegmenting] = useState(false);
  const [segmentProgress, setSegmentProgress] = useState<string | null>(null);

  const placedNames = new Set(placedJoints.map((j) => j.name));

  const handleSegment = useCallback(async () => {
    if (placedJoints.length < 2) return;

    setSegmenting(true);
    setSegmentProgress("Submitting segmentation...");

    try {
      const jointsMap: Record<string, { x: number; y: number; z: number }> = {};
      for (const j of placedJoints) {
        jointsMap[j.name] = { x: j.position[0], y: j.position[1], z: j.position[2] };
      }

      const result = await segmentWithJoints(
        {
          mesh_path: meshPath,
          joints: jointsMap,
          target_height: actionFigureSettings.targetHeight,
          clearance: actionFigureSettings.clearance,
        },
        (msg) => setSegmentProgress(msg),
      );

      onSegmentComplete?.(result.result || "Segmentation complete");
    } catch (err) {
      onSegmentComplete?.(
        err instanceof Error ? err.message : "Segmentation failed",
      );
    } finally {
      setSegmenting(false);
      setSegmentProgress(null);
    }
  }, [placedJoints, meshPath, actionFigureSettings, onSegmentComplete]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="relative p-4">
        <div className="flex items-center justify-between mb-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">
            Place Joints
          </p>
          <button
            onClick={onBack}
            className="text-[11px] font-medium text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
          >
            â† Back
          </button>
        </div>
        <p className="text-[12px] text-[var(--chat-muted)] leading-relaxed">
          Select a joint type, then click on the model to place it.
        </p>
        <div className="absolute bottom-0 left-3 right-3 divider" />
      </div>

      {/* Joint list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-px scrollbar-thin">
        {JOINT_TYPES.map((name) => {
          const isPlaced = placedNames.has(name);
          const isActive = activeJoint === name;

          return (
            <div
              key={name}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-md text-[13px] transition-colors cursor-pointer",
                isActive
                  ? "bg-[var(--chat-accent-soft)] text-[var(--chat-accent-strong)]"
                  : isPlaced
                  ? "text-[var(--chat-text)] hover:bg-[var(--hover-tint)]"
                  : "text-[var(--chat-muted)] hover:bg-[var(--hover-tint)] hover:text-[var(--chat-text)]",
              )}
              onClick={() => setActiveJoint(isActive ? null : (name as JointName))}
            >
              <span
                className={cn(
                  "w-2 h-2 rounded-full flex-shrink-0",
                  JOINT_COLORS[name] || "bg-[var(--chat-muted)]",
                )}
              />
              <span className="flex-1">{JOINT_LABELS[name] || name}</span>
              {isPlaced ? (
                <div className="flex items-center gap-1.5">
                  <Check size={13} className="text-emerald-400" />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeJoint(name);
                    }}
                    className="text-[var(--chat-subtle)] hover:text-red-400 transition-colors"
                    aria-label={`Remove ${JOINT_LABELS[name] || name}`}
                  >
                    <X size={13} />
                  </button>
                </div>
              ) : isActive ? (
                <Crosshair size={13} className="text-[var(--chat-accent)] animate-pulse" />
              ) : null}
            </div>
          );
        })}
      </div>

      {/* Actions */}
      <div className="relative p-4 space-y-2">
        <div className="absolute top-0 left-3 right-3 divider" />
        <div className="flex items-center justify-between text-[11px] text-[var(--chat-muted)] tabular-nums">
          <span>
            <span className="text-[var(--chat-text)] font-medium">{placedJoints.length}</span>
            <span className="text-[var(--chat-subtle)]"> / {JOINT_TYPES.length} placed</span>
          </span>
          {placedJoints.length > 0 && (
            <button
              onClick={clearJoints}
              className="inline-flex items-center gap-1 text-[var(--chat-subtle)] hover:text-red-400 transition-colors"
            >
              <RotateCcw size={11} />
              Clear all
            </button>
          )}
        </div>

        <button
          onClick={handleSegment}
          disabled={placedJoints.length < 2 || segmenting}
          className={cn(
            "w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-md text-[13px] font-medium transition-all",
            placedJoints.length >= 2 && !segmenting ? "btn-primary" : "btn-secondary cursor-not-allowed",
          )}
        >
          {segmenting ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              <span className="truncate">{segmentProgress || "Segmenting…"}</span>
            </>
          ) : (
            <>
              <Scissors size={14} />
              <span>Segment into Parts</span>
            </>
          )}
        </button>

        <p className="text-[10px] text-[var(--chat-subtle)] text-center">
          Place at least 2 joints. More joints = more parts.
        </p>
      </div>
    </div>
  );
}
