"use client";

import { useState, useEffect } from "react";
import {
  startTraining,
  fetchCuratedDatasets,
  fetchTemplates,
  type StartTrainingRequest,
  type CuratedDataset,
  type Template,
} from "@/lib/api/training";
import { Rocket, Clock, Cpu, Database, Zap, Loader2, BookOpen, ShieldCheck, Sparkles, Filter } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const RUN_TYPES = [
  {
    value: "full_pipeline" as const,
    label: "Full Pipeline",
    desc: "Export traces from Langfuse, then train on exported data",
    icon: Zap,
  },
  {
    value: "curated" as const,
    label: "Curated Datasets",
    desc: "Download verified HuggingFace datasets, security-scan, then train",
    icon: BookOpen,
  },
  {
    value: "synthetic" as const,
    label: "Synthetic Generation",
    desc: "Generate diverse tool-use trajectories via local Ollama, then train",
    icon: Sparkles,
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
  { label: "15 min", value: 15, estimate: "~30-50 min total" },
  { label: "30 min", value: 30, estimate: "~45-65 min total" },
  { label: "1 hour", value: 60, estimate: "~80-110 min total" },
  { label: "2 hours", value: 120, estimate: "~140-170 min total" },
  { label: "4 hours", value: 240, estimate: "~260-290 min total" },
  { label: "No limit", value: null, estimate: "Runs until all epochs complete" },
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

  // Curated dataset state
  const [curatedList, setCuratedList] = useState<CuratedDataset[]>([]);
  const [selectedDatasets, setSelectedDatasets] = useState<Set<string>>(
    new Set(["glaive-function-calling", "hermes-function-calling"])
  );
  const [maxSamples, setMaxSamples] = useState("");
  const [syntheticTarget, setSyntheticTarget] = useState("552");

  // Template filter state
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);

  useEffect(() => {
    fetchCuratedDatasets().then(setCuratedList);
    fetchTemplates().then(setTemplates);
  }, []);

  const toggleDataset = (key: string) => {
    setSelectedDatasets((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleTemplateSelect = (templateId: string | null) => {
    setSelectedTemplate(templateId);
    // Auto-suggest datasets when selecting a template in curated mode
    if (runType === "curated" && templateId && curatedList.length > 0) {
      const recommended = curatedList
        .filter((ds) => ds.recommended_for?.includes(templateId))
        .map((ds) => ds.key);
      if (recommended.length > 0) {
        setSelectedDatasets(new Set(recommended));
      }
    }
  };

  const handleLaunch = async () => {
    setLaunching(true);
    setResult(null);

    const req: StartTrainingRequest = {
      run_type: runType,
      time_budget_minutes: timeBudget,
    };

    if (selectedTemplate && (runType === "full_pipeline" || runType === "export" || runType === "curated")) {
      req.template_id = selectedTemplate;
    }

    if (runType === "curated") {
      req.curated_datasets = Array.from(selectedDatasets);
      const samples = parseInt(maxSamples);
      if (samples > 0) req.max_samples = samples;
    }

    if (runType === "synthetic") {
      const target = parseInt(syntheticTarget);
      if (target > 0) req.synthetic_target = target;
    }

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
          <h1 className="text-lg font-semibold text-[var(--chat-text)]">
            Launch Training Run
          </h1>
        </div>

        {/* Run Type Selection */}
        <div className="space-y-3">
          <label className="text-sm font-medium text-[var(--chat-muted)]">Run Type</label>
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
                      ? "border-[var(--chat-accent)]/30 bg-[var(--chat-accent)]/5"
                      : "border-[var(--chat-border)] hover:border-[var(--chat-border)] bg-transparent"
                  )}
                >
                  <Icon
                    size={18}
                    className={cn(
                      "mt-0.5 shrink-0",
                      selected ? "text-[var(--chat-accent)]" : "text-[var(--chat-muted)]"
                    )}
                  />
                  <div>
                    <p
                      className={cn(
                        "text-sm font-medium",
                        selected ? "text-[var(--chat-accent)]" : "text-[var(--chat-text)]"
                      )}
                    >
                      {rt.label}
                    </p>
                    <p className="text-xs text-[var(--chat-muted)] mt-0.5">{rt.desc}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Template Filter ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â for Full Pipeline, Export, and Curated */}
        {(runType === "full_pipeline" || runType === "export" || runType === "curated") && templates.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Filter size={14} className="text-[var(--chat-accent)]" />
              <label className="text-sm font-medium text-[var(--chat-muted)]">
                Train Toward Agent
              </label>
              <span className="text-xs text-[var(--chat-muted)]">(optional)</span>
            </div>
            <p className="text-xs text-[var(--chat-muted)]">
              {runType === "curated"
                ? "Select an agent to auto-suggest the most relevant datasets for improving that agent\u2019s capabilities."
                : "Filter exported traces to only include data from a specific agent template. This focuses training on improving that agent\u2019s capabilities."}
            </p>
            <div className="grid gap-2">
              <button
                onClick={() => handleTemplateSelect(null)}
                className={cn(
                  "flex items-start gap-3 p-3 rounded-lg border text-left transition-colors",
                  selectedTemplate === null
                    ? "border-[var(--chat-accent)]/20 bg-[var(--chat-accent)]/5"
                    : "border-[var(--chat-border)] hover:border-[var(--chat-border)] bg-transparent"
                )}
              >
                <div className={cn(
                  "mt-0.5 w-4 h-4 rounded-full border flex items-center justify-center shrink-0",
                  selectedTemplate === null ? "border-[var(--chat-accent)] bg-cyan-500" : "border-[var(--chat-border)]"
                )}>
                  {selectedTemplate === null && <div className="w-2 h-2 rounded-full bg-white" />}
                </div>
                <div>
                  <p className={cn("text-sm font-medium", selectedTemplate === null ? "text-[var(--chat-accent)]" : "text-[var(--chat-text)]")}>
                    All Agents
                  </p>
                  <p className="text-xs text-[var(--chat-muted)] mt-0.5">Use traces from every agent template</p>
                </div>
              </button>
              {templates.map((t) => {
                const selected = selectedTemplate === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => handleTemplateSelect(t.id)}
                    className={cn(
                      "flex items-start gap-3 p-3 rounded-lg border text-left transition-colors",
                      selected
                        ? "border-[var(--chat-accent)]/20 bg-[var(--chat-accent)]/5"
                        : "border-[var(--chat-border)] hover:border-[var(--chat-border)] bg-transparent"
                    )}
                  >
                    <div className={cn(
                      "mt-0.5 w-4 h-4 rounded-full border flex items-center justify-center shrink-0",
                      selected ? "border-[var(--chat-accent)] bg-cyan-500" : "border-[var(--chat-border)]"
                    )}>
                      {selected && <div className="w-2 h-2 rounded-full bg-white" />}
                    </div>
                    <div>
                      <p className={cn("text-sm font-medium", selected ? "text-[var(--chat-accent)]" : "text-[var(--chat-text)]")}>
                        {t.id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                      </p>
                      <p className="text-xs text-[var(--chat-muted)] mt-0.5">
                        {t.intent}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Curated Dataset Selection */}
        {runType === "curated" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <ShieldCheck size={14} className="text-emerald-500" />
              <label className="text-sm font-medium text-[var(--chat-muted)]">
                Select Datasets
              </label>
              <span className="text-xs text-[var(--chat-muted)]">
                (all samples are security-scanned before training)
              </span>
            </div>
            <div className="grid gap-2">
              {curatedList.map((ds) => {
                const checked = selectedDatasets.has(ds.key);
                const isRecommended = selectedTemplate != null && ds.recommended_for?.includes(selectedTemplate);
                return (
                  <button
                    key={ds.key}
                    onClick={() => toggleDataset(ds.key)}
                    className={cn(
                      "flex items-start gap-3 p-3 rounded-lg border text-left transition-colors",
                      checked
                        ? "border-emerald-500/40 bg-emerald-500/5"
                        : isRecommended
                          ? "border-[var(--chat-accent)]/15 bg-[var(--chat-accent)]/5 hover:border-[var(--chat-accent)]/20"
                          : "border-[var(--chat-border)] hover:border-[var(--chat-border)] bg-transparent"
                    )}
                  >
                    <div
                      className={cn(
                        "mt-0.5 w-4 h-4 rounded border flex items-center justify-center shrink-0",
                        checked
                          ? "border-emerald-500 bg-emerald-500"
                          : "border-[var(--chat-border)]"
                      )}
                    >
                      {checked && (
                        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className={cn("text-sm font-medium", checked ? "text-emerald-300" : "text-[var(--chat-text)]")}>
                          {ds.key}
                        </p>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--chat-surface)] text-[var(--chat-muted)]">
                          {ds.category}
                        </span>
                        {isRecommended && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--chat-accent)]/10 text-[var(--chat-accent)] border border-[var(--chat-accent)]/15">
                            Recommended
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-[var(--chat-muted)] mt-0.5">{ds.description}</p>
                      <p className="text-[10px] text-[var(--chat-muted)] mt-0.5">
                        HF: {ds.hf_id} &middot; default: {ds.default_max.toLocaleString()} samples
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
            {selectedDatasets.size === 0 && (
              <p className="text-xs text-amber-400">Select at least one dataset</p>
            )}
            <div className="flex items-center gap-2">
              <input
                type="number"
                placeholder="Max samples per dataset..."
                value={maxSamples}
                onChange={(e) => setMaxSamples(e.target.value)}
                className="w-56 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg px-3 py-2 text-sm text-[var(--chat-text)] placeholder:text-[var(--chat-muted)] focus:outline-none focus:border-emerald-500/50"
              />
              <span className="text-xs text-[var(--chat-muted)]">per dataset (blank = default)</span>
            </div>
          </div>
        )}

        {/* Synthetic Generation Options */}
        {runType === "synthetic" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-violet-400" />
              <label className="text-sm font-medium text-[var(--chat-muted)]">
                Generation Target
              </label>
            </div>
            <p className="text-xs text-[var(--chat-muted)]">
              Generates diverse tool-use problems (code, file ops, IoT, research)
              using local Ollama, scores them with the reward function, and keeps
              only high-quality trajectories. All output is security-scanned before training.
            </p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={syntheticTarget}
                onChange={(e) => setSyntheticTarget(e.target.value)}
                className="w-32 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg px-3 py-2 text-sm text-[var(--chat-text)] focus:outline-none focus:border-violet-500/50"
              />
              <span className="text-xs text-[var(--chat-muted)]">
                trajectories (default 552, per ToolOrchestra research)
              </span>
            </div>
          </div>
        )}

        {/* Time Budget */}
        {runType !== "export" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Clock size={14} className="text-[var(--chat-muted)]" />
              <label className="text-sm font-medium text-[var(--chat-muted)]">
                Training Time Budget
              </label>
            </div>
            <p className="text-xs text-[var(--chat-muted)]">
              Time budget controls active training only. Total wall-clock time
              also includes model loading (~10-30 min cached, up to 60 min cold)
              and dataset preparation. Estimates assume Qwen3.6-27B QLoRA on
              Lovelace’s RTX 5060 Ti (32 GB VRAM).
            </p>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
              {TIME_PRESETS.map((preset) => {
                const isSelected = timeBudget === preset.value && !customTime;
                return (
                  <button
                    key={preset.label}
                    onClick={() => {
                      setTimeBudget(preset.value);
                      setCustomTime("");
                    }}
                    className={cn(
                      "px-3 py-2 rounded-lg border transition-colors text-left",
                      isSelected
                        ? "border-[var(--chat-accent)]/30 bg-[var(--chat-accent)]/10"
                        : "border-[var(--chat-border)] hover:border-[var(--chat-border)] bg-transparent"
                    )}
                  >
                    <span className={cn("text-xs font-medium block", isSelected ? "text-[var(--chat-accent)]" : "text-[var(--chat-muted)]")}>
                      {preset.label}
                    </span>
                    <span className="text-[10px] text-[var(--chat-muted)] block mt-0.5">
                      {preset.estimate}
                    </span>
                  </button>
                );
              })}
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
                className="w-48 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg px-3 py-2 text-sm text-[var(--chat-text)] placeholder:text-[var(--chat-muted)] focus:outline-none focus:border-[var(--chat-accent)]"
              />
              <span className="text-xs text-[var(--chat-muted)]">minutes (training only)</span>
            </div>
            {timeBudget && (
              <p className="text-xs text-[var(--chat-muted)]">
                Training stops after {timeBudget} min of active training.
                Checkpoints saved every 50 steps. Estimated total time:{" "}
                <span className="text-[var(--chat-muted)]">
                  {timeBudget + 15}&ndash;{timeBudget + 40} min
                </span>{" "}
                (including model load + dataset prep on Lovelace).
              </p>
            )}
          </div>
        )}

        {/* Advanced Options */}
        {runType !== "export" && (
          <div className="space-y-3">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-[var(--chat-muted)] hover:text-[var(--chat-muted)] transition-colors"
            >
              {showAdvanced ? "Hide" : "Show"} advanced options
            </button>
            {showAdvanced && (
              <div className="grid grid-cols-3 gap-4 border border-[var(--chat-border)] rounded-lg p-4">
                <div>
                  <label className="text-xs text-[var(--chat-muted)] block mb-1">
                    LoRA Rank
                  </label>
                  <input
                    type="number"
                    value={loraRank}
                    onChange={(e) => setLoraRank(e.target.value)}
                    className="w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-[var(--chat-accent)]"
                  />
                </div>
                <div>
                  <label className="text-xs text-[var(--chat-muted)] block mb-1">
                    Learning Rate
                  </label>
                  <input
                    type="text"
                    value={learningRate}
                    onChange={(e) => setLearningRate(e.target.value)}
                    className="w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-[var(--chat-accent)]"
                  />
                </div>
                <div>
                  <label className="text-xs text-[var(--chat-muted)] block mb-1">
                    Epochs
                  </label>
                  <input
                    type="number"
                    value={epochs}
                    onChange={(e) => setEpochs(e.target.value)}
                    className="w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded px-3 py-1.5 text-sm text-[var(--chat-text)] focus:outline-none focus:border-[var(--chat-accent)]"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Launch Button */}
        <button
          onClick={handleLaunch}
          disabled={launching || (runType === "curated" && selectedDatasets.size === 0)}
          className={cn(
            "w-full flex items-center justify-center gap-2 py-3 rounded-lg text-sm font-medium transition-colors",
            launching
              ? "bg-[var(--chat-surface)] text-[var(--chat-muted)] cursor-not-allowed"
              : "bg-[var(--chat-accent)] hover:bg-[var(--chat-accent-strong)] text-white"
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
