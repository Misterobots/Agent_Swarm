"use client";

import { useState } from "react";
import { startTraining, type StartTrainingRequest } from "@/lib/api/training";
import { Rocket, Clock, Cpu, Database, Zap, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const RUN_TYPES = [
  {
    value: "full_pipeline" as const,
    label: "Full Pipeline",
    desc: "Export traces from Langfuse, then train on exported data",
    icon: Zap,
  },
  {
    value: "training" as const,
    label: "Train Only",
    desc: "Train on existing dataset (skip export step)",
    icon: Cpu,
  },
  {
    value: "export" as const,
    label: "Export Only",
    desc: "Export high-reward traces to JSONL without training",
    icon: Database,
  },
];

const TIME_PRESETS = [
  { label: "15 min", value: 15 },
  { label: "30 min", value: 30 },
  { label: "1 hour", value: 60 },
  { label: "2 hours", value: 120 },
  { label: "4 hours", value: 240 },
  { label: "No limit", value: null },
];

export function TrainingLauncher() {
  const [runType, setRunType] = useState<StartTrainingRequest["run_type"]>("full_pipeline");
  const [timeBudget, setTimeBudget] = useState<number | null>(60);
  const [customTime, setCustomTime] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loraRank, setLoraRank] = useState("16");
  const [learningRate, setLearningRate] = useState("5e-6");
  const [epochs, setEpochs] = useState("3");
  const [launching, setLaunching] = useState(false);
  const [result, setResult] = useState<{
    status: string;
    error?: string;
  } | null>(null);

  const handleLaunch = async () => {
    setLaunching(true);
    setResult(null);

    const req: StartTrainingRequest = {
      run_type: runType,
      time_budget_minutes: timeBudget,
    };

    if (showAdvanced) {
      req.lora_rank = parseInt(loraRank) || null;
      req.learning_rate = parseFloat(learningRate) || null;
      req.epochs = parseInt(epochs) || null;
    }

    const res = await startTraining(req);
    setResult(res);
    setLaunching(false);
  };

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="max-w-2xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Rocket size={20} className="text-violet-400" />
          <h1 className="text-lg font-semibold text-zinc-100">
            Launch Training Run
          </h1>
        </div>

        {/* Run Type Selection */}
        <div className="space-y-3">
          <label className="text-sm font-medium text-zinc-400">Run Type</label>
          <div className="grid gap-3">
            {RUN_TYPES.map((rt) => {
              const Icon = rt.icon;
              const selected = runType === rt.value;
              return (
                <button
                  key={rt.value}
                  onClick={() => setRunType(rt.value)}
                  className={cn(
                    "flex items-start gap-3 p-4 rounded-lg border text-left transition-colors",
                    selected
                      ? "border-cyan-500/50 bg-cyan-500/5"
                      : "border-zinc-800 hover:border-zinc-700 bg-transparent"
                  )}
                >
                  <Icon
                    size={18}
                    className={cn(
                      "mt-0.5 shrink-0",
                      selected ? "text-cyan-400" : "text-zinc-600"
                    )}
                  />
                  <div>
                    <p
                      className={cn(
                        "text-sm font-medium",
                        selected ? "text-cyan-300" : "text-zinc-300"
                      )}
                    >
                      {rt.label}
                    </p>
                    <p className="text-xs text-zinc-600 mt-0.5">{rt.desc}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Time Budget */}
        {runType !== "export" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Clock size={14} className="text-zinc-500" />
              <label className="text-sm font-medium text-zinc-400">
                Time Budget
              </label>
            </div>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
              {TIME_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  onClick={() => {
                    setTimeBudget(preset.value);
                    setCustomTime("");
                  }}
                  className={cn(
                    "px-3 py-2 text-xs rounded-lg border transition-colors",
                    timeBudget === preset.value && !customTime
                      ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-300"
                      : "border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700"
                  )}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                placeholder="Custom minutes..."
                value={customTime}
                onChange={(e) => {
                  setCustomTime(e.target.value);
                  const val = parseFloat(e.target.value);
                  setTimeBudget(val > 0 ? val : null);
                }}
                className="w-48 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-700 focus:outline-none focus:border-cyan-500/50"
              />
              <span className="text-xs text-zinc-600">minutes</span>
            </div>
            {timeBudget && (
              <p className="text-xs text-zinc-600">
                Training will automatically stop after {timeBudget} minutes.
                Checkpoints are saved every 50 steps so no progress is lost.
              </p>
            )}
          </div>
        )}

        {/* Advanced Options */}
        {runType !== "export" && (
          <div className="space-y-3">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors"
            >
              {showAdvanced ? "Hide" : "Show"} advanced options
            </button>
            {showAdvanced && (
              <div className="grid grid-cols-3 gap-4 border border-zinc-800 rounded-lg p-4">
                <div>
                  <label className="text-xs text-zinc-600 block mb-1">
                    LoRA Rank
                  </label>
                  <input
                    type="number"
                    value={loraRank}
                    onChange={(e) => setLoraRank(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-cyan-500/50"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-600 block mb-1">
                    Learning Rate
                  </label>
                  <input
                    type="text"
                    value={learningRate}
                    onChange={(e) => setLearningRate(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-cyan-500/50"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-600 block mb-1">
                    Epochs
                  </label>
                  <input
                    type="number"
                    value={epochs}
                    onChange={(e) => setEpochs(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-cyan-500/50"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Launch Button */}
        <button
          onClick={handleLaunch}
          disabled={launching}
          className={cn(
            "w-full flex items-center justify-center gap-2 py-3 rounded-lg text-sm font-medium transition-colors",
            launching
              ? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
              : "bg-cyan-600 hover:bg-cyan-500 text-white"
          )}
        >
          {launching ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Starting...
            </>
          ) : (
            <>
              <Rocket size={16} />
              Launch{" "}
              {RUN_TYPES.find((r) => r.value === runType)?.label ?? "Training"}
            </>
          )}
        </button>

        {/* Result Banner */}
        {result && (
          <div
            className={cn(
              "border rounded-lg p-4",
              result.status === "error" || result.error
                ? "border-red-500/30 bg-red-500/5"
                : "border-emerald-500/30 bg-emerald-500/5"
            )}
          >
            {result.error ? (
              <p className="text-sm text-red-400">{result.error}</p>
            ) : (
              <p className="text-sm text-emerald-400">
                Training run started successfully. Check the Overview tab for
                progress.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
