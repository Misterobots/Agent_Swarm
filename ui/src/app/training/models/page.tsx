"use client";

import Link from "next/link";
import { FlaskConical, History, RefreshCw, Sparkles } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { fetchModelCatalog } from "@/lib/api/training";
import { useCallback, useEffect, useState } from "react";
import type { ModelCatalog } from "@/types/ops";

// ── helpers ──────────────────────────────────────────────────

function fmtSize(mb: number) {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

// ── page ─────────────────────────────────────────────────────
export default function TrainingModelsPage() {
  const [catalog, setCatalog] = useState<ModelCatalog>({
    ollama_models: [],
    local_gguf: [],
    errors: [],
  });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const c = await fetchModelCatalog();
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
      title="Model Catalog"
      description="Deployed Ollama models, local GGUF files, and training pipeline reference."
      icon={FlaskConical}
    >
      {/* Refresh */}
      <div className="mb-2 flex items-center justify-end">
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] transition-colors hover:text-[var(--chat-text)] disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Run History quick-link */}
      <WorkspaceSection title="Training Runs">
        <Link
          href="/training/runs"
          className="flex items-center gap-3 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-4 py-3 hover:border-[var(--chat-accent)] hover:bg-[var(--chat-surface)] transition-colors group"
        >
          <History size={16} className="text-[var(--chat-muted)] group-hover:text-[var(--chat-accent)] transition-colors shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-[var(--chat-text)]">View Run History</p>
            <p className="text-xs text-[var(--chat-muted)]">All training runs with live metrics, convert-to-Ollama, and A/B deploy actions</p>
          </div>
          <span className="text-xs text-[var(--chat-muted)] group-hover:text-[var(--chat-accent)] transition-colors">&rarr;</span>
        </Link>
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
              color: "border-[var(--chat-accent)]/30 bg-[var(--chat-accent)]/8",
            },
            {
              step: "3. A/B Test",
              cmd: "python -m training.ab_test start <template_id> <candidate>",
              color: "border-emerald-900/60 bg-emerald-950/20",
            },
          ].map(({ step, cmd, color }) => (
            <div key={step} className={`rounded-lg border p-3 ${color}`}>
              <p className="mb-2 text-xs font-semibold text-[var(--chat-text)]">{step}</p>
              <code className="block text-xs text-[var(--chat-muted)] break-all">{cmd}</code>
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
          <div className="overflow-x-auto rounded-lg border border-[var(--chat-border)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--chat-border)] bg-[var(--chat-surface)]">
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">Model</th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">
                    Run ID
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">Size</th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)] hidden md:table-cell">
                    Path
                  </th>
                </tr>
              </thead>
              <tbody>
                {catalog.local_gguf.map((g) => (
                  <tr key={g.path} className="border-b border-[var(--chat-border)] hover:bg-[var(--chat-surface)]">
                    <td className="px-4 py-2.5 font-mono text-xs text-[var(--chat-text)]">{g.name}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-[var(--chat-muted)]">{g.run_id}</td>
                    <td className="px-4 py-2.5 text-xs text-[var(--chat-muted)]">{fmtSize(g.size_mb)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-[var(--chat-muted)] hidden md:table-cell">
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
        description="Live models available across both inference nodes."
      >
        {catalog.errors.length > 0 && (
          <div className="mb-3 rounded-lg border border-yellow-900/60 bg-yellow-950/30 px-4 py-2 text-xs text-yellow-400">
            {catalog.errors.join(" · ")}
          </div>
        )}
        {loading && catalog.ollama_models.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--chat-muted)]">Querying Ollama nodes…</p>
        ) : catalog.ollama_models.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--chat-muted)]">
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
                  <p className="mb-2 text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wide">
                    {label}
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-[var(--chat-border)]">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[var(--chat-border)] bg-[var(--chat-surface)]">
                          <th className="px-4 py-2 text-left text-xs font-medium text-[var(--chat-muted)]">
                            Model
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-[var(--chat-muted)]">
                            Size
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-[var(--chat-muted)] hidden md:table-cell">
                            Digest
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-[var(--chat-muted)] hidden sm:table-cell">
                            Modified
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {models.map((m) => (
                          <tr
                            key={`${m.node}-${m.name}`}
                            className="border-b border-[var(--chat-border)] hover:bg-[var(--chat-surface)]"
                          >
                            <td className="px-4 py-2 font-mono text-xs text-[var(--chat-text)]">
                              {m.name}
                            </td>
                            <td className="px-4 py-2 text-xs text-[var(--chat-muted)]">
                              {fmtSize(m.size_mb)}
                            </td>
                            <td className="px-4 py-2 font-mono text-xs text-[var(--chat-muted)] hidden md:table-cell">
                              {m.digest}
                            </td>
                            <td className="px-4 py-2 text-xs text-[var(--chat-muted)] hidden sm:table-cell">
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
        <div className="rounded-lg border border-dashed border-[var(--chat-border)] bg-[var(--chat-panel)] px-5 py-6 text-center">
          <Sparkles size={20} className="mx-auto mb-2 text-[var(--chat-muted)]" />
          <p className="text-sm font-medium text-[var(--chat-muted)]">Model promotion workflow</p>
          <p className="mt-1 text-xs text-[var(--chat-muted)] max-w-sm mx-auto">
            Once a GGUF file exists and an expertise template is configured, a promotion button
            will appear here to run{" "}
            <code className="text-[var(--chat-muted)]">ollama create</code> and start an A/B test via{" "}
            <code className="text-[var(--chat-muted)]">training.ab_test</code>.
          </p>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
