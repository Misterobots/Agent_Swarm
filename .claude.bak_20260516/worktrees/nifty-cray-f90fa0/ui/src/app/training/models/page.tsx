"use client";

import Link from "next/link";
import { ArrowRight, FlaskConical, History, RefreshCw, Sparkles } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { Button, Card } from "@/components/ui";
import { fetchModelCatalog } from "@/lib/api/training";
import { useCallback, useEffect, useState } from "react";
import type { ModelCatalog } from "@/types/ops";
import { cn } from "@/lib/utils/cn";

function fmtSize(mb: number) {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

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
      actions={
        <Button
          variant="secondary"
          size="sm"
          onClick={load}
          iconLeft={<RefreshCw size={13} className={loading ? "animate-spin" : ""} />}
        >
          Refresh
        </Button>
      }
    >
      <WorkspaceSection title="Training Runs">
        <Link
          href="/training/runs"
          className="lift group surface block p-4 transition-colors hover:border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
        >
          <div className="flex items-start gap-3">
            <div
              className="w-9 h-9 rounded-md flex items-center justify-center flex-shrink-0 text-[var(--chat-accent)]"
              style={{
                background: "linear-gradient(135deg, var(--chat-accent-soft), color-mix(in srgb, var(--chat-accent) 4%, transparent))",
                border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
              }}
            >
              <History size={16} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--chat-text)]">View Run History</p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-[var(--chat-muted)]">
                All training runs with live metrics, convert-to-Ollama, and A/B deploy actions.
              </p>
            </div>
            <ArrowRight
              size={15}
              className="mt-2 shrink-0 text-[var(--chat-muted)] transition-all group-hover:text-[var(--chat-accent)] group-hover:translate-x-0.5"
            />
          </div>
        </Link>
      </WorkspaceSection>

      <WorkspaceSection
        title="Training Pipeline"
        description="CLI commands to advance a run through the full GRPO → GGUF → Ollama pipeline."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { step: "1. GRPO Fine-tune",  cmd: "python -m training.grpo_trainer --dataset training_data/grpo_traces.jsonl" },
            { step: "2. Convert to GGUF", cmd: "python -m training.convert_gguf --adapter training_output/<run>/adapter" },
            { step: "3. A/B Test",        cmd: "python -m training.ab_test start <template_id> <candidate>" },
          ].map(({ step, cmd }) => (
            <Card key={step} padding="md">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
                {step}
              </p>
              <code
                className="mt-2 block rounded-sm px-2.5 py-2 text-[11px] font-mono text-[var(--chat-text)] break-all leading-relaxed"
                style={{
                  background: "var(--chat-bg)",
                  border: "1px solid var(--chat-border)",
                  boxShadow: "inset 0 1px 2px rgba(0,0,0,0.15)",
                }}
              >
                {cmd}
              </code>
            </Card>
          ))}
        </div>
      </WorkspaceSection>

      {catalog.local_gguf.length > 0 && (
        <WorkspaceSection
          title="Local GGUF Files"
          description="Converted models in the training output directory — ready for Ollama import."
        >
          <ModelTable
            columns={["Model", "Run ID", "Size", "Path"]}
            mdHidden={[3]}
            rows={catalog.local_gguf.map((g) => [
              <span key="n" className="font-mono">{g.name}</span>,
              <span key="r" className="font-mono text-[var(--chat-muted)]">{g.run_id}</span>,
              <span key="s" className="tabular-nums text-[var(--chat-muted)]">{fmtSize(g.size_mb)}</span>,
              <span key="p" className="font-mono text-[var(--chat-muted)] truncate inline-block max-w-md">{g.path}</span>,
            ])}
          />
        </WorkspaceSection>
      )}

      <WorkspaceSection
        title="Model Catalog — Deployed (Ollama)"
        description="Live models available across both inference nodes."
      >
        {catalog.errors.length > 0 && (
          <div
            className="mb-3 rounded-md px-4 py-2.5 text-[13px]"
            style={{
              background: "color-mix(in srgb, #facc15 8%, var(--chat-surface))",
              border: "1px solid color-mix(in srgb, #facc15 35%, var(--chat-border))",
              color: "#facc15",
            }}
          >
            {catalog.errors.join(" · ")}
          </div>
        )}
        {loading && catalog.ollama_models.length === 0 ? (
          <Card padding="lg" className="text-center">
            <p className="text-sm text-[var(--chat-muted)]">Querying Ollama nodes…</p>
          </Card>
        ) : catalog.ollama_models.length === 0 ? (
          <Card padding="lg" className="text-center">
            <p className="text-sm text-[var(--chat-muted)]">
              No Ollama models found (nodes may be offline or OLLAMA_HOST unconfigured).
            </p>
          </Card>
        ) : (
          <div className="space-y-5">
            {[
              { label: "Execution Plane", models: execModels },
              { label: "Control Plane", models: ctrlModels },
            ]
              .filter(({ models }) => models.length > 0)
              .map(({ label, models }) => (
                <div key={label}>
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">
                    {label}
                  </p>
                  <ModelTable
                    columns={["Model", "Size", "Digest", "Modified"]}
                    mdHidden={[2]}
                    smHidden={[3]}
                    rows={models.map((m) => [
                      <span key="n" className="font-mono">{m.name}</span>,
                      <span key="s" className="tabular-nums text-[var(--chat-muted)]">{fmtSize(m.size_mb)}</span>,
                      <span key="d" className="font-mono text-[var(--chat-muted)] truncate inline-block max-w-[160px]">{m.digest}</span>,
                      <span key="m" className="tabular-nums text-[var(--chat-muted)]">{m.modified_at ? new Date(m.modified_at).toLocaleDateString() : "—"}</span>,
                    ])}
                  />
                </div>
              ))}
          </div>
        )}
      </WorkspaceSection>

      <WorkspaceSection
        title="Model Promotion"
        description="Promote a trained GGUF into the live Ollama catalog and trigger A/B traffic splitting."
      >
        <Card padding="lg" className="text-center border-dashed">
          <div
            className="w-10 h-10 rounded-md mx-auto mb-3 flex items-center justify-center text-[var(--chat-accent)]"
            style={{
              background: "var(--chat-accent-soft)",
              border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
            }}
          >
            <Sparkles size={18} />
          </div>
          <p className="text-sm font-medium text-[var(--chat-text)]">Model promotion workflow</p>
          <p className="mt-1.5 text-[12px] text-[var(--chat-muted)] max-w-md mx-auto leading-relaxed">
            Once a GGUF file exists and an expertise template is configured, a promotion button will
            appear here to run <code className="text-[var(--chat-text)] font-mono">ollama create</code> and
            start an A/B test via <code className="text-[var(--chat-text)] font-mono">training.ab_test</code>.
          </p>
        </Card>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}

/** Reusable table for the various model lists on this page. */
function ModelTable({
  columns,
  rows,
  mdHidden = [],
  smHidden = [],
}: {
  columns: string[];
  rows: React.ReactNode[][];
  mdHidden?: number[];
  smHidden?: number[];
}) {
  const hiddenClass = (i: number) =>
    cn(mdHidden.includes(i) && "hidden md:table-cell", smHidden.includes(i) && "hidden sm:table-cell");
  return (
    <div className="surface overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr
              className="border-b border-[var(--chat-border)]"
              style={{ background: "color-mix(in srgb, var(--chat-panel) 60%, transparent)" }}
            >
              {columns.map((c, i) => (
                <th
                  key={c}
                  className={cn(
                    "px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]",
                    hiddenClass(i),
                  )}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr
                key={ri}
                className={cn(
                  "transition-colors hover:bg-[var(--hover-tint)]",
                  ri !== rows.length - 1 && "border-b border-[var(--divider)]",
                )}
              >
                {row.map((cell, ci) => (
                  <td key={ci} className={cn("px-4 py-2.5 text-[12px] text-[var(--chat-text)]", hiddenClass(ci))}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
