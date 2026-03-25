"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchTrainingRuns,
  fetchConvertReport,
  fetchTemplates,
  startConvert,
  startDeploy,
  type ConvertReport,
  type Template,
} from "@/lib/api/training";
import type { TrainingRun } from "@/types/training";
import {
  History,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Package,
  Rocket,
  Loader2,
} from "lucide-react";
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
                          {run.status === "completed" &&
                            run.run_type !== "conversion" && (
                              <RunActions runId={run.id} />
                            )}
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
import { ConvertReportView } from "./convert-report";
import { DeployReportView } from "./deploy-report";

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

/**
 * Action buttons shown below a completed training run's report.
 * - "Convert to Ollama Model" when no model version exists
 * - "Deploy for A/B Testing" when converted but not yet deployed
 */
function RunActions({ runId }: { runId: number }) {
  const [convertReport, setConvertReport] = useState<ConvertReport | null>(
    null
  );
  const [convertChecked, setConvertChecked] = useState(false);
  const [converting, setConverting] = useState(false);
  const [convertError, setConvertError] = useState<string | null>(null);
  const [showConvertForm, setShowConvertForm] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState("");

  const [deploying, setDeploying] = useState(false);
  const [deployError, setDeployError] = useState<string | null>(null);
  const [showDeployForm, setShowDeployForm] = useState(false);
  const [deployed, setDeployed] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [trafficSplit, setTrafficSplit] = useState(0.2);
  const [minInvocations, setMinInvocations] = useState(100);

  // Check if conversion already exists for this run
  useEffect(() => {
    fetchConvertReport(runId).then((r) => {
      setConvertReport(r);
      setConvertChecked(true);
    });
  }, [runId]);

  const hasConversion =
    convertReport?.status === "completed" && convertReport.model_version;
  const conversionRunning = converting || convertReport?.status === "running";

  const handleConvert = async () => {
    setConverting(true);
    setConvertError(null);
    const res = await startConvert({
      training_run_id: runId,
      system_prompt: systemPrompt || null,
    });
    if (res.status === "error" && "error" in res) {
      setConvertError(res.error ?? "Unknown error");
      setConverting(false);
    }
    // Poll for completion
    setShowConvertForm(false);
  };

  const handleDeploy = async () => {
    if (!selectedTemplate) return;
    setDeploying(true);
    setDeployError(null);
    const res = await startDeploy({
      training_run_id: runId,
      template_id: selectedTemplate,
      traffic_split: trafficSplit,
      min_invocations: minInvocations,
    });
    setDeploying(false);
    if ("error" in res && res.status === "error") {
      setDeployError(
        typeof res.error === "string" ? res.error : "Unknown error"
      );
    } else {
      setDeployed(true);
      setShowDeployForm(false);
    }
  };

  const openDeployForm = async () => {
    if (templates.length === 0) {
      const t = await fetchTemplates();
      setTemplates(t);
      if (t.length > 0 && !selectedTemplate) setSelectedTemplate(t[0].id);
    }
    setShowDeployForm(true);
  };

  if (!convertChecked) return null;

  return (
    <div className="mt-4 space-y-3">
      {/* Divider */}
      <div className="border-t border-zinc-800 pt-3">
        <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-2">
          Actions
        </p>
      </div>

      {/* Convert Button / Report */}
      {!hasConversion && !conversionRunning && (
        <>
          {!showConvertForm ? (
            <button
              onClick={() => setShowConvertForm(true)}
              className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 transition-colors"
            >
              <Package size={14} />
              Convert to Ollama Model
            </button>
          ) : (
            <div className="border border-zinc-800 rounded-lg p-3 space-y-3">
              <p className="text-xs text-zinc-400 font-medium">
                Convert to Ollama Model
              </p>
              <div>
                <label className="text-[10px] text-zinc-600 block mb-1">
                  System Prompt (optional)
                </label>
                <input
                  type="text"
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="e.g. You are a helpful coding assistant..."
                  className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-300 placeholder-zinc-600"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleConvert}
                  className="px-3 py-1.5 text-xs rounded bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 transition-colors"
                >
                  Start Conversion
                </button>
                <button
                  onClick={() => setShowConvertForm(false)}
                  className="px-3 py-1.5 text-xs rounded text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {convertError && (
        <p className="text-xs text-red-400">{convertError}</p>
      )}

      {/* Show convert report when converting or completed */}
      {(conversionRunning || hasConversion) && (
        <ConvertReportView runId={runId} />
      )}

      {/* Deploy Button / Report */}
      {hasConversion && !deployed && (
        <>
          {!showDeployForm ? (
            <button
              onClick={openDeployForm}
              className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg border border-violet-500/30 text-violet-400 hover:bg-violet-500/10 transition-colors"
            >
              <Rocket size={14} />
              Deploy for A/B Testing
            </button>
          ) : (
            <div className="border border-zinc-800 rounded-lg p-3 space-y-3">
              <p className="text-xs text-zinc-400 font-medium">
                Deploy for A/B Testing
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] text-zinc-600 block mb-1">
                    Template
                  </label>
                  <select
                    value={selectedTemplate}
                    onChange={(e) => setSelectedTemplate(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-300"
                  >
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.id} ({t.intent})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-zinc-600 block mb-1">
                    Traffic Split
                  </label>
                  <select
                    value={trafficSplit}
                    onChange={(e) =>
                      setTrafficSplit(parseFloat(e.target.value))
                    }
                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-300"
                  >
                    <option value={0.1}>10% candidate</option>
                    <option value={0.2}>20% candidate</option>
                    <option value={0.3}>30% candidate</option>
                    <option value={0.5}>50% candidate</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-zinc-600 block mb-1">
                    Min Invocations
                  </label>
                  <input
                    type="number"
                    value={minInvocations}
                    onChange={(e) =>
                      setMinInvocations(parseInt(e.target.value) || 100)
                    }
                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-300"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleDeploy}
                  disabled={deploying || !selectedTemplate}
                  className="px-3 py-1.5 text-xs rounded bg-violet-500/20 text-violet-400 hover:bg-violet-500/30 transition-colors disabled:opacity-50"
                >
                  {deploying ? (
                    <span className="flex items-center gap-1">
                      <Loader2 size={12} className="animate-spin" /> Deploying...
                    </span>
                  ) : (
                    "Start A/B Test"
                  )}
                </button>
                <button
                  onClick={() => setShowDeployForm(false)}
                  className="px-3 py-1.5 text-xs rounded text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {deployError && (
        <p className="text-xs text-red-400">{deployError}</p>
      )}

      {/* Show deploy report when deployed */}
      {deployed && <DeployReportView runId={runId} />}
    </div>
  );
}
