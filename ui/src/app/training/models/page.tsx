"use client";

import { BookOpen, CheckCircle2, ChevronRight, FlaskConical, RefreshCw, Sparkles } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { fetchModelCatalog, fetchTrainingRuns } from "@/lib/api/training";
import { useCallback, useEffect, useState } from "react";
import type { ModelCatalog, TrainingRun } from "@/types/ops";

// ── helpers ──────────────────────────────────────────────────────────────
function RunStatusBadge({ status }: { status: TrainingRun["status"] }) {
  const map = {
    in_progress: "text-yellow-400 border-yellow-900/60 bg-yellow-950/30",
    complete: "text-emerald-400 border-emerald-900/60 bg-emerald-950/20",
    converted: "text-cyan-400 border-cyan-900/60 bg-cyan-950/20",
  } as const;
  const label = {
    in_progress: "In Progress",
    complete: "Adapter Ready",
    converted: "GGUF Converted",
  } as const;
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-xs ${map[status]}`}>
      {label[status]}
    </span>
  );
}

function NodeBadge({ node }: { node: string }) {
  return node === "execution-plane" ? (
    <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400">Exec</span>
  ) : (
    <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-cyan-500">Ctrl</span>
  );
}

function fmtSize(mb: number) {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

// ── page ─────────────────────────────────────────────────────────────────
export default function TrainingModelsPage() {
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [catalog, setCatalog] = useState<ModelCatalog>({
    ollama_models: [],
    local_gguf: [],
    errors: [],
  });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [r, c] = await Promise.all([fetchTrainingRuns(), fetchModelCatalog()]);
    setRuns(r);
    setCatalog(c);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const execModels = catalog.ollama_models.filter((m) => m.node === "execution-plane");
  const ctrlModels = catalog.ollama_models.filter((m) => m.node === "control-plane");

  return (
    <WorkspaceShell
      title="Model Training"
      description="Training runs, adapter management, GGUF conversion, and deployed model catalog."
      icon={FlaskConical}
    >
      {/* Refresh */}
      <div className="mb-6 flex items-center justify-end">
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-400 transition-colors hover:text-zinc-200 disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Training Runs */}
      <WorkspaceSection
        title="Training Runs"
        description="QLoRA/GRPO runs from agents/training/grpo_trainer.py stored in the training output directory."
      >
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/80">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">Run ID</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">
                  Base Model
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400 hidden sm:table-cell">
                  Started
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">Status</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400 hidden md:table-cell">
                  GGUF Files
                </th>
              </tr>
            </thead>
            <tbody>
              {loading && runs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-zinc-500">
                    Loading training runs…
                  </td>
                </tr>
              ) : runs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-zinc-500">
                    No training runs found in{" "}
                    <code className="text-xs">TRAINING_OUTPUT_DIR</code>. Run{" "}
                    <code className="text-xs">
                      python -m training.grpo_trainer --dataset …
                    </code>{" "}
                    to start one.
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr key={run.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                    <td className="px-4 py-2.5 font-mono text-xs text-zinc-200">{run.id}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400">{run.base_model}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-500 hidden sm:table-cell">
                      {run.started_at ?? "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-2.5 hidden md:table-cell">
                      {run.gguf_files.length > 0 ? (
                        <ul className="space-y-0.5">
                          {run.gguf_files.map((f) => (
                            <li key={f} className="font-mono text-xs text-cyan-400">
                              {f}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-xs text-zinc-600">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </WorkspaceSection>

      {/* Training pipeline quick-ref */}
      <WorkspaceSection
        title="Training Pipeline"
        description="CLI commands to advance a run through the full GRPO → GGUF → Ollama pipeline."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            {
              step: "1. GRPO Fine-tune",
              cmd: "python -m training.grpo_trainer --dataset training_data/grpo_traces.jsonl",
              color: "border-violet-900/60 bg-violet-950/20",
            },
            {
              step: "2. Convert to GGUF",
              cmd: "python -m training.convert_gguf --adapter training_output/<run>/adapter",
              color: "border-cyan-900/60 bg-cyan-950/20",
            },
            {
              step: "3. A/B Test",
              cmd: "python -m training.ab_test start <template_id> <candidate>",
              color: "border-emerald-900/60 bg-emerald-950/20",
            },
          ].map(({ step, cmd, color }) => (
            <div key={step} className={`rounded-lg border p-3 ${color}`}>
              <p className="mb-2 text-xs font-semibold text-zinc-300">{step}</p>
              <code className="block text-xs text-zinc-400 break-all">{cmd}</code>
            </div>
          ))}
        </div>
      </WorkspaceSection>

      {/* Local GGUF files */}
      {catalog.local_gguf.length > 0 && (
        <WorkspaceSection
          title="Local GGUF Files"
          description="Converted models in the training output directory — ready for Ollama import."
        >
          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/80">
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">Model</th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">
                    Run ID
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">Size</th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400 hidden md:table-cell">
                    Path
                  </th>
                </tr>
              </thead>
              <tbody>
                {catalog.local_gguf.map((g) => (
                  <tr key={g.path} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                    <td className="px-4 py-2.5 font-mono text-xs text-zinc-200">{g.name}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-zinc-500">{g.run_id}</td>
                    <td className="px-4 py-2.5 text-xs text-zinc-400">{fmtSize(g.size_mb)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-zinc-600 hidden md:table-cell">
                      {g.path}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </WorkspaceSection>
      )}

      {/* Model Catalog — Ollama */}
      <WorkspaceSection
        title="Model Catalog — Deployed (Ollama)"
        description="Live models available across both inference nodes. Future: promote a GGUF here via ollama create."
      >
        {catalog.errors.length > 0 && (
          <div className="mb-3 rounded-lg border border-yellow-900/60 bg-yellow-950/30 px-4 py-2 text-xs text-yellow-400">
            {catalog.errors.join(" · ")}
          </div>
        )}
        {loading && catalog.ollama_models.length === 0 ? (
          <p className="py-6 text-center text-sm text-zinc-500">Querying Ollama nodes…</p>
        ) : catalog.ollama_models.length === 0 ? (
          <p className="py-6 text-center text-sm text-zinc-500">
            No Ollama models found (nodes may be offline or OLLAMA_HOST unconfigured).
          </p>
        ) : (
          <div className="space-y-4">
            {[
              { label: "Execution Plane", models: execModels },
              { label: "Control Plane", models: ctrlModels },
            ]
              .filter(({ models }) => models.length > 0)
              .map(({ label, models }) => (
                <div key={label}>
                  <p className="mb-2 text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                    {label}
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-zinc-800">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-zinc-800 bg-zinc-900/80">
                          <th className="px-4 py-2 text-left text-xs font-medium text-zinc-400">
                            Model
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-zinc-400">
                            Size
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-zinc-400 hidden md:table-cell">
                            Digest
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-zinc-400 hidden sm:table-cell">
                            Modified
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {models.map((m) => (
                          <tr
                            key={`${m.node}-${m.name}`}
                            className="border-b border-zinc-800/50 hover:bg-zinc-800/30"
                          >
                            <td className="px-4 py-2 font-mono text-xs text-zinc-200">
                              {m.name}
                            </td>
                            <td className="px-4 py-2 text-xs text-zinc-400">
                              {fmtSize(m.size_mb)}
                            </td>
                            <td className="px-4 py-2 font-mono text-xs text-zinc-600 hidden md:table-cell">
                              {m.digest}
                            </td>
                            <td className="px-4 py-2 text-xs text-zinc-500 hidden sm:table-cell">
                              {m.modified_at
                                ? new Date(m.modified_at).toLocaleDateString()
                                : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
          </div>
        )}
      </WorkspaceSection>

      {/* Future: Model Promotion */}
      <WorkspaceSection
        title="Model Promotion (Planned)"
        description="Promote a trained GGUF into the live Ollama catalog and trigger A/B traffic splitting."
      >
        <div className="rounded-lg border border-dashed border-zinc-700 bg-zinc-900/30 px-5 py-6 text-center">
          <Sparkles size={20} className="mx-auto mb-2 text-zinc-600" />
          <p className="text-sm font-medium text-zinc-400">Model promotion workflow</p>
          <p className="mt-1 text-xs text-zinc-600 max-w-sm mx-auto">
            Once a GGUF file exists and an expertise template is configured, a promotion button
            will appear here to run{" "}
            <code className="text-zinc-500">ollama create</code> and start an A/B test via{" "}
            <code className="text-zinc-500">training.ab_test</code>.
          </p>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
