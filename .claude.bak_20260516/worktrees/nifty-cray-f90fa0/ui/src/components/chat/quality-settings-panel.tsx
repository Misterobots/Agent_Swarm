"use client";

import { Clock, Zap, Layers, ShieldCheck, Wrench, Repeat } from "lucide-react";
import { useSettingsStore } from "@/lib/stores/settings-store";

// Proportional split of the overall time budget when used as a preset.
// Biased toward generation-heavy agents; verifier is typically a short scoring pass.
const SOLVER_SHARE = 0.4;
const VERIFIER_SHARE = 0.2;
const CORRECTOR_SHARE = 0.4;

export function QualitySettingsPanel() {
  const mode = useSettingsStore((s) => s.mode);
  const solvingMaxIter = useSettingsStore((s) => s.solvingMaxIter);
  const solvingMaxTime = useSettingsStore((s) => s.solvingMaxTime);
  const setSolvingMaxIter = useSettingsStore((s) => s.setSolvingMaxIter);
  const setSolvingMaxTime = useSettingsStore((s) => s.setSolvingMaxTime);

  const solvingSolverNDrafts = useSettingsStore((s) => s.solvingSolverNDrafts);
  const solvingSolverMaxTime = useSettingsStore((s) => s.solvingSolverMaxTime);
  const solvingVerifierNRuns = useSettingsStore((s) => s.solvingVerifierNRuns);
  const solvingVerifierMaxTime = useSettingsStore((s) => s.solvingVerifierMaxTime);
  const solvingCorrectorNPasses = useSettingsStore((s) => s.solvingCorrectorNPasses);
  const solvingCorrectorMaxTime = useSettingsStore((s) => s.solvingCorrectorMaxTime);
  const setSolvingSolverNDrafts = useSettingsStore((s) => s.setSolvingSolverNDrafts);
  const setSolvingSolverMaxTime = useSettingsStore((s) => s.setSolvingSolverMaxTime);
  const setSolvingVerifierNRuns = useSettingsStore((s) => s.setSolvingVerifierNRuns);
  const setSolvingVerifierMaxTime = useSettingsStore((s) => s.setSolvingVerifierMaxTime);
  const setSolvingCorrectorNPasses = useSettingsStore((s) => s.setSolvingCorrectorNPasses);
  const setSolvingCorrectorMaxTime = useSettingsStore((s) => s.setSolvingCorrectorMaxTime);

  const isDevMode = mode === "developer";

  // Overall time slider in dev mode acts as a "preset" that proportionally splits
  // across the three per-agent sliders. Snapping to 30s steps matches the slider step.
  const snap30 = (v: number) => Math.round(v / 30) * 30;
  const applyOverallPreset = (totalSeconds: number) => {
    setSolvingMaxTime(totalSeconds);
    if (!isDevMode) return;
    if (totalSeconds === 0) {
      setSolvingSolverMaxTime(0);
      setSolvingVerifierMaxTime(0);
      setSolvingCorrectorMaxTime(0);
      return;
    }
    setSolvingSolverMaxTime(snap30(totalSeconds * SOLVER_SHARE));
    setSolvingVerifierMaxTime(snap30(totalSeconds * VERIFIER_SHARE));
    setSolvingCorrectorMaxTime(snap30(totalSeconds * CORRECTOR_SHARE));
  };

  // Moving any granular slider updates the overall slider to reflect the new sum.
  const setSolverWithSync = (v: number) => {
    setSolvingSolverMaxTime(v);
    setSolvingMaxTime(v + solvingVerifierMaxTime + solvingCorrectorMaxTime);
  };
  const setVerifierWithSync = (v: number) => {
    setSolvingVerifierMaxTime(v);
    setSolvingMaxTime(solvingSolverMaxTime + v + solvingCorrectorMaxTime);
  };
  const setCorrectorWithSync = (v: number) => {
    setSolvingCorrectorMaxTime(v);
    setSolvingMaxTime(solvingSolverMaxTime + solvingVerifierMaxTime + v);
  };

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
            {solvingMaxIter === 0 ? "0" : solvingMaxIter}
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
          {solvingMaxIter === 0 && "No verification — fastest, accepts solver output as-is"}
          {solvingMaxIter === 1 && "Single verify pass — quick check, no correction"}
          {solvingMaxIter === 2 && "Default — verify, correct once if needed, verify again"}
          {solvingMaxIter >= 3 && solvingMaxIter <= 5 && "Higher quality — more correction rounds"}
          {solvingMaxIter > 5 && "Maximum quality — thorough refinement"}
        </p>
      </div>

      {/* Time Limit Slider */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-[var(--chat-muted)] flex items-center gap-1">
            <Clock size={12} />
            Max Time (seconds){isDevMode && " — preset"}
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
          value={Math.min(solvingMaxTime, 300)}
          onChange={(e) => applyOverallPreset(parseInt(e.target.value, 10))}
          className="w-full h-1.5 bg-[var(--chat-border)] rounded-lg appearance-none cursor-pointer accent-[var(--chat-accent)]"
        />
        <div className="flex justify-between text-xs text-[var(--chat-muted)] mt-0.5">
          <span>No limit (0)</span>
          <span>5 min (300s)</span>
        </div>
        <p className="text-xs text-[var(--chat-muted)] mt-1">
          {!isDevMode && solvingMaxTime === 0 && "No time limit — process until done"}
          {!isDevMode && solvingMaxTime > 0 && solvingMaxTime <= 60 && "Fast timeout — quick responses"}
          {!isDevMode && solvingMaxTime > 60 && solvingMaxTime <= 180 && "Moderate timeout"}
          {!isDevMode && solvingMaxTime > 180 && "Extended timeout — complex tasks"}
          {isDevMode && "Moving this preset proportionally fills the per-agent sliders below (40/20/40)."}
        </p>
      </div>

      {/* Developer-mode granular per-agent budgets */}
      {isDevMode && (
        <div className="pt-2 mt-2 border-t border-[var(--chat-border)] space-y-2">
          <div className="text-xs font-medium text-[var(--chat-text)] flex items-center gap-1">
            <span className="px-1.5 py-0.5 rounded bg-[var(--chat-accent)]/15 text-[var(--chat-accent)] text-[10px] uppercase tracking-wide">Dev</span>
            Per-agent budgets
          </div>

          {/* Solver: Best-of-N drafts */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-[var(--chat-muted)] flex items-center gap-1">
                <Layers size={12} />
                Solver — Best-of-N drafts
              </label>
              <span className="text-xs text-[var(--chat-text)] font-mono">{solvingSolverNDrafts}</span>
            </div>
            <input
              type="range"
              min="1"
              max="3"
              step="1"
              value={solvingSolverNDrafts}
              onChange={(e) => setSolvingSolverNDrafts(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-[var(--chat-border)] rounded-lg appearance-none cursor-pointer accent-[var(--chat-accent)]"
            />
            <p className="text-xs text-[var(--chat-muted)] mt-1">
              {solvingSolverNDrafts === 1 && "Single solver pass (today's behavior)"}
              {solvingSolverNDrafts === 2 && "2 drafts — verifier picks the winner. ~2× solver cost"}
              {solvingSolverNDrafts === 3 && "3 drafts — verifier picks the winner. ~3× solver cost"}
            </p>
          </div>

          {/* Solver: per-call wall clock */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-[var(--chat-muted)] flex items-center gap-1">
                <Clock size={12} />
                Solver — Max Time
              </label>
              <span className="text-xs text-[var(--chat-text)] font-mono">
                {solvingSolverMaxTime === 0 ? "∞" : `${solvingSolverMaxTime}s`}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="300"
              step="30"
              value={Math.min(solvingSolverMaxTime, 300)}
              onChange={(e) => setSolverWithSync(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-[var(--chat-border)] rounded-lg appearance-none cursor-pointer accent-[var(--chat-accent)]"
            />
          </div>

          {/* Verifier: consensus runs */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-[var(--chat-muted)] flex items-center gap-1">
                <Repeat size={12} />
                Verifier — Consensus Runs
              </label>
              <span className="text-xs text-[var(--chat-text)] font-mono">{solvingVerifierNRuns}</span>
            </div>
            <input
              type="range"
              min="1"
              max="5"
              step="1"
              value={solvingVerifierNRuns}
              onChange={(e) => setSolvingVerifierNRuns(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-[var(--chat-border)] rounded-lg appearance-none cursor-pointer accent-[var(--chat-accent)]"
            />
            <p className="text-xs text-[var(--chat-muted)] mt-1">
              {solvingVerifierNRuns === 1 && "Single pass (standard behavior)"}
              {solvingVerifierNRuns === 2 && "2-way consensus — majority vote (2/2 = pass)"}
              {solvingVerifierNRuns === 3 && "3-way consensus — majority vote (≥2/3 = pass)"}
              {solvingVerifierNRuns >= 4 && `${solvingVerifierNRuns}-way consensus — stronger signal, higher cost`}
            </p>
          </div>

          {/* Verifier: per-call wall clock */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-[var(--chat-muted)] flex items-center gap-1">
                <ShieldCheck size={12} />
                Verifier — Max Time
              </label>
              <span className="text-xs text-[var(--chat-text)] font-mono">
                {solvingVerifierMaxTime === 0 ? "∞" : `${solvingVerifierMaxTime}s`}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="300"
              step="30"
              value={Math.min(solvingVerifierMaxTime, 300)}
              onChange={(e) => setVerifierWithSync(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-[var(--chat-border)] rounded-lg appearance-none cursor-pointer accent-[var(--chat-accent)]"
            />
          </div>

          {/* Corrector: refinement passes */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-[var(--chat-muted)] flex items-center gap-1">
                <Repeat size={12} />
                Corrector — Refinement Passes
              </label>
              <span className="text-xs text-[var(--chat-text)] font-mono">{solvingCorrectorNPasses}</span>
            </div>
            <input
              type="range"
              min="1"
              max="3"
              step="1"
              value={solvingCorrectorNPasses}
              onChange={(e) => setSolvingCorrectorNPasses(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-[var(--chat-border)] rounded-lg appearance-none cursor-pointer accent-[var(--chat-accent)]"
            />
            <p className="text-xs text-[var(--chat-muted)] mt-1">
              {solvingCorrectorNPasses === 1 && "Single pass (standard behavior)"}
              {solvingCorrectorNPasses === 2 && "2 sequential passes — each refines the previous output"}
              {solvingCorrectorNPasses === 3 && "3 sequential passes — thorough refinement, ~3× corrector cost"}
            </p>
          </div>

          {/* Corrector: per-call wall clock */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-[var(--chat-muted)] flex items-center gap-1">
                <Wrench size={12} />
                Corrector — Max Time
              </label>
              <span className="text-xs text-[var(--chat-text)] font-mono">
                {solvingCorrectorMaxTime === 0 ? "∞" : `${solvingCorrectorMaxTime}s`}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="300"
              step="30"
              value={Math.min(solvingCorrectorMaxTime, 300)}
              onChange={(e) => setCorrectorWithSync(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-[var(--chat-border)] rounded-lg appearance-none cursor-pointer accent-[var(--chat-accent)]"
            />
          </div>

          <p className="text-xs text-[var(--chat-muted)]">
            Granular caps override the overall preset. Per-call timeouts use a worker-thread guard;
            the underlying LLM call may still finish server-side, we just stop waiting.
          </p>
        </div>
      )}

      <div className="text-xs text-[var(--chat-muted)] pt-1 border-t border-[var(--chat-border)]">
        💡 These settings control MarsRL loop behavior. Higher values = better quality but longer processing time.
      </div>
    </div>
  );
}
