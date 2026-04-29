"use client";

import { Clock, Zap } from "lucide-react";
import { useSettingsStore } from "@/lib/stores/settings-store";

export function QualitySettingsPanel() {
  const solvingMaxIter = useSettingsStore((s) => s.solvingMaxIter);
  const solvingMaxTime = useSettingsStore((s) => s.solvingMaxTime);
  const setSolvingMaxIter = useSettingsStore((s) => s.setSolvingMaxIter);
  const setSolvingMaxTime = useSettingsStore((s) => s.setSolvingMaxTime);

  return (
    <div className="space-y-2">
      {/* Iterations Slider */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-[var(--chat-muted)] flex items-center gap-1">
            <Zap size={12} />
            Max Iterations
          </label>
          <span className="text-xs text-[var(--chat-text)] font-mono">
            {solvingMaxIter === 0 ? "∞" : solvingMaxIter}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="10"
          step="1"
          value={solvingMaxIter}
          onChange={(e) => setSolvingMaxIter(parseInt(e.target.value, 10))}
          className="w-full h-1.5 bg-[var(--chat-border)] rounded-lg appearance-none cursor-pointer accent-[var(--chat-accent)]"
        />
        <div className="flex justify-between text-xs text-[var(--chat-muted)] mt-0.5">
          <span>Quick (0)</span>
          <span>Thorough (10)</span>
        </div>
        <p className="text-xs text-[var(--chat-muted)] mt-1">
          {solvingMaxIter === 0 && "Unlimited iterations - fastest response"}
          {solvingMaxIter === 1 && "Single pass - quick but less refined"}
          {solvingMaxIter === 2 && "Default - balanced quality"}
          {solvingMaxIter >= 3 && solvingMaxIter <= 5 && "Higher quality - more refinement"}
          {solvingMaxIter > 5 && "Maximum quality - thorough refinement"}
        </p>
      </div>

      {/* Time Limit Slider */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-[var(--chat-muted)] flex items-center gap-1">
            <Clock size={12} />
            Max Time (seconds)
          </label>
          <span className="text-xs text-[var(--chat-text)] font-mono">
            {solvingMaxTime === 0 ? "∞" : `${solvingMaxTime}s`}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="300"
          step="30"
          value={solvingMaxTime}
          onChange={(e) => setSolvingMaxTime(parseInt(e.target.value, 10))}
          className="w-full h-1.5 bg-[var(--chat-border)] rounded-lg appearance-none cursor-pointer accent-[var(--chat-accent)]"
        />
        <div className="flex justify-between text-xs text-[var(--chat-muted)] mt-0.5">
          <span>No limit (0)</span>
          <span>5 min (300s)</span>
        </div>
        <p className="text-xs text-[var(--chat-muted)] mt-1">
          {solvingMaxTime === 0 && "No time limit - process until done"}
          {solvingMaxTime > 0 && solvingMaxTime <= 60 && "Fast timeout - quick responses"}
          {solvingMaxTime > 60 && solvingMaxTime <= 180 && "Moderate timeout"}
          {solvingMaxTime > 180 && "Extended timeout - complex tasks"}
        </p>
      </div>

      <div className="text-xs text-[var(--chat-muted)] pt-1 border-t border-[var(--chat-border)]">
        💡 These settings control MarsRL loop behavior. Higher values = better quality but longer processing time.
      </div>
    </div>
  );
}
