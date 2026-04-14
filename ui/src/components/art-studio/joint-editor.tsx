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
      <div className="p-4 border-b border-[var(--chat-border)]">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-[var(--chat-text)]">Place Joints</h2>
          <button
            onClick={onBack}
            className="text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
          >
            â† Back
          </button>
        </div>
        <p className="text-xs text-[var(--chat-muted)]">
          Select a joint type, then click on the model to place it.
        </p>
      </div>

      {/* Joint list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {JOINT_TYPES.map((name) => {
          const isPlaced = placedNames.has(name);
          const isActive = activeJoint === name;

          return (
            <div
              key={name}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all cursor-pointer",
                isActive
                  ? "bg-violet-600/30 border border-violet-500 text-white"
                  : isPlaced
                  ? "bg-[var(--chat-surface)] text-[var(--chat-text)] hover:bg-[var(--chat-surface)]"
                  : "text-[var(--chat-muted)] hover:bg-[var(--chat-surface)] hover:text-[var(--chat-text)]",
              )}
              onClick={() => setActiveJoint(isActive ? null : (name as JointName))}
            >
              {/* Color dot */}
              <span
                className={cn(
                  "w-2.5 h-2.5 rounded-full flex-shrink-0",
                  JOINT_COLORS[name] || "bg-[var(--chat-muted)]",
                )}
              />

              {/* Label */}
              <span className="flex-1">{JOINT_LABELS[name] || name}</span>

              {/* Status */}
              {isPlaced ? (
                <div className="flex items-center gap-1">
                  <Check size={14} className="text-emerald-400" />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeJoint(name);
                    }}
                    className="text-[var(--chat-muted)] hover:text-red-400 transition-colors"
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : isActive ? (
                <Crosshair size={14} className="text-violet-400 animate-pulse" />
              ) : null}
            </div>
          );
        })}
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-[var(--chat-border)] space-y-2">
        <div className="flex items-center justify-between text-xs text-[var(--chat-muted)] mb-2">
          <span>
            {placedJoints.length} / {JOINT_TYPES.length} joints placed
          </span>
          {placedJoints.length > 0 && (
            <button
              onClick={clearJoints}
              className="flex items-center gap-1 text-[var(--chat-muted)] hover:text-red-400 transition-colors"
            >
              <RotateCcw size={12} />
              Clear all
            </button>
          )}
        </div>

        <button
          onClick={handleSegment}
          disabled={placedJoints.length < 2 || segmenting}
          className={cn(
            "w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all",
            placedJoints.length >= 2 && !segmenting
              ? "bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-900/30"
              : "bg-[var(--chat-surface)] text-[var(--chat-muted)] cursor-not-allowed",
          )}
        >
          {segmenting ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              {segmentProgress || "Segmenting..."}
            </>
          ) : (
            <>
              <Scissors size={16} />
              Segment into Parts
            </>
          )}
        </button>

        <p className="text-[10px] text-[var(--chat-muted)] text-center">
          Place at least 2 joints. More joints = more parts.
        </p>
      </div>
    </div>
  );
}
