"use client";

import { ChevronDown, ExternalLink, Radar, RefreshCw, Search } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { Button, Card } from "@/components/ui";
import { fetchTraceDetail, fetchTraces } from "@/lib/api/ops";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Observation, Trace, TraceDetail } from "@/types/ops";
import { cn } from "@/lib/utils/cn";

// ── helpers ──────────────────────────────────────────────────────────────
function levelClass(level: string) {
  if (level === "ERROR") return "bg-red-500/15 text-red-400";
  if (level === "WARNING") return "bg-yellow-500/15 text-yellow-400";
  return "bg-emerald-500/15 text-emerald-400";
}

function fmtLatency(ms: number | null) {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`;
}

function fmtTs(ts: string | null) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function spanDuration(obs: Observation): string {
  if (!obs.startTime || !obs.endTime) return "";
  try {
    const start = new Date(obs.startTime).getTime();
    const end = new Date(obs.endTime).getTime();
    const ms = end - start;
    return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
  } catch {
    return "";
  }
}

// ── sub-components ────────────────────────────────────────────────────────
function CodeBlock({ children }: { children: React.ReactNode }) {
  return (
    <pre
      className="overflow-x-auto rounded-sm px-3 py-2 text-[11px] font-mono text-[var(--chat-text)] whitespace-pre-wrap max-h-48 leading-relaxed"
      style={{
        background: "var(--chat-bg)",
        border: "1px solid var(--chat-border)",
        boxShadow: "inset 0 1px 2px rgba(0,0,0,0.15)",
      }}
    >
      {children}
    </pre>
  );
}

function ObservationRow({ obs }: { obs: Observation }) {
  const [open, setOpen] = useState(false);
  const isError = obs.level === "ERROR";
  const duration = spanDuration(obs);
  const tok = obs.usage
    ? [
        obs.usage.input != null && `In: ${obs.usage.input}`,
        obs.usage.output != null && `Out: ${obs.usage.output}`,
        obs.usage.totalCost != null && `$${obs.usage.totalCost.toFixed(4)}`,
      ]
        .filter(Boolean)
        .join(" / ")
    : "";

  return (
    <div className="surface overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-[var(--hover-tint)]"
      >
        <span
          className={cn(
            "w-1.5 h-1.5 rounded-full flex-shrink-0",
            isError ? "bg-red-400" : "bg-emerald-400"
          )}
        />
        <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--chat-subtle)] flex-shrink-0">
          {obs.type}
        </span>
        <span className="flex-1 text-[12px] text-[var(--chat-text)] truncate">
          {obs.name}
          {obs.model && (
            <span className="ml-2 font-mono text-[var(--chat-accent)]">· {obs.model}</span>
          )}
        </span>
        {duration && (
          <span className="text-[11px] tabular-nums text-[var(--chat-muted)] flex-shrink-0">
            {duration}
          </span>
        )}
        {tok && (
          <span className="text-[11px] text-[var(--chat-muted)] hidden md:inline flex-shrink-0">
            {tok}
          </span>
        )}
        <ChevronDown
          size={13}
          className={cn(
            "transition-transform text-[var(--chat-subtle)] flex-shrink-0",
            open && "rotate-180"
          )}
        />
      </button>

      {open && (
        <div className="border-t border-[var(--chat-border)] px-3 py-3 space-y-3 bg-[color:color-mix(in_srgb,var(--chat-soft)_50%,transparent)]">
          {obs.input != null && (
            <div>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
                Input / Prompt
              </p>
              <CodeBlock>
                {typeof obs.input === "string" ? obs.input : JSON.stringify(obs.input, null, 2)}
              </CodeBlock>
            </div>
          )}
          {obs.output != null && (
            <div>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
                Output / Response
              </p>
              <CodeBlock>
                {typeof obs.output === "string" ? obs.output : JSON.stringify(obs.output, null, 2)}
              </CodeBlock>
            </div>
          )}
          {obs.metadata != null && (
            <div>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
                Metadata
              </p>
              <CodeBlock>{JSON.stringify(obs.metadata, null, 2)}</CodeBlock>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TraceInspector({
  traceId,
  langfuseUrl,
}: {
  traceId: string;
  langfuseUrl?: string;
}) {
  const [detail, setDetail] = useState<TraceDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setDetail(null);
    setLoading(true);
    fetchTraceDetail(traceId).then((d) => {
      setDetail(d);
      setLoading(false);
    });
  }, [traceId]);

  if (loading) {
    return (
      <Card padding="lg" className="text-center">
        <p className="text-sm text-[var(--chat-muted)]">Loading trace detail…</p>
      </Card>
    );
  }
  if (!detail) {
    return (
      <Card padding="lg" className="text-center">
        <p className="text-sm text-red-400">Failed to load trace detail.</p>
      </Card>
    );
  }

  const { trace, observations } = detail;

  return (
    <div className="space-y-4">
      <Card padding="md">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-[12px] sm:grid-cols-4">
            <MetaField label="Name">{String(trace.name ?? "—")}</MetaField>
            <MetaField label="Status">{String(trace.level ?? "DEFAULT")}</MetaField>
            <MetaField label="Latency">
              <span className="tabular-nums">{fmtLatency(typeof trace.latency === "number" ? trace.latency : null)}</span>
            </MetaField>
            <MetaField label="Timestamp">
              <span className="tabular-nums">{fmtTs(typeof trace.timestamp === "string" ? trace.timestamp : null)}</span>
            </MetaField>
          </div>
          {(langfuseUrl ?? detail.langfuse_url) && (
            <a
              href={langfuseUrl ?? detail.langfuse_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex shrink-0 items-center gap-1 text-[12px] font-medium text-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)] transition-colors"
            >
              Open in Langfuse <ExternalLink size={12} />
            </a>
          )}
        </div>
        {trace.input != null && (
          <div className="mt-3 pt-3 border-t border-[var(--chat-border)]">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
              Root Input
            </p>
            <CodeBlock>
              {typeof trace.input === "string" ? trace.input : JSON.stringify(trace.input, null, 2)}
            </CodeBlock>
          </div>
        )}
      </Card>

      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">
          Observations · {observations.length} span{observations.length !== 1 ? "s" : ""}
        </p>
        {observations.length === 0 ? (
          <Card padding="md" className="text-center">
            <p className="text-xs text-[var(--chat-muted)]">No observations recorded for this trace.</p>
          </Card>
        ) : (
          <div className="space-y-1.5">
            {observations.map((obs) => (
              <ObservationRow key={obs.id} obs={obs} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MetaField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">{label}</span>
      <span className="text-[var(--chat-text)] font-medium">{children}</span>
    </>
  );
}

// ── page ─────────────────────────────────────────────────────────────────
export default function SwarmObserverPage() {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Trace | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchTraces(100);
    setTraces(result.data);
    setError(result.error ?? null);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    if (!search.trim()) return traces;
    const q = search.toLowerCase();
    return traces.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.id.toLowerCase().includes(q) ||
        t.input_preview.toLowerCase().includes(q)
    );
  }, [traces, search]);

  return (
    <WorkspaceShell
      title="Swarm Observer"
      description="Live trace feed from Langfuse — inspect agent spans, model calls, and latency."
      icon={Radar}
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
      {/* Toolbar */}
      <div className="mb-4 flex items-center gap-2">
        <div className="relative flex-1">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--chat-subtle)] pointer-events-none"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by trace name, ID, or content…"
            className="input-field w-full !py-2 pl-9 text-[13px]"
          />
        </div>
      </div>

      {error && (
        <div
          className="mb-4 rounded-md px-4 py-2.5 text-[13px]"
          style={{
            background: "color-mix(in srgb, #facc15 8%, var(--chat-surface))",
            border: "1px solid color-mix(in srgb, #facc15 35%, var(--chat-border))",
            color: "#facc15",
          }}
        >
          {error}
        </div>
      )}

      <WorkspaceSection
        title={`Trace Feed${filtered.length !== traces.length ? ` — ${filtered.length} of ${traces.length}` : ` — ${traces.length} traces`}`}
      >
        <div className="surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="border-b border-[var(--chat-border)]"
                  style={{ background: "color-mix(in srgb, var(--chat-panel) 60%, transparent)" }}
                >
                  <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">Agent / Name</th>
                  <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)] hidden sm:table-cell">Input Preview</th>
                  <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)] w-24">Latency</th>
                  <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)] w-20">Level</th>
                  <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)] w-32 hidden md:table-cell">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {loading && traces.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-[var(--chat-muted)]">
                      Loading traces…
                    </td>
                  </tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-[var(--chat-muted)]">
                      {error
                        ? "Langfuse unreachable — check LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY."
                        : "No traces match your filter."}
                    </td>
                  </tr>
                ) : (
                  filtered.map((t, i) => (
                    <tr
                      key={t.id}
                      onClick={() => setSelected(selected?.id === t.id ? null : t)}
                      className={cn(
                        "cursor-pointer transition-colors",
                        i !== filtered.length - 1 && "border-b border-[var(--divider)]",
                        selected?.id === t.id
                          ? "bg-[var(--chat-accent-soft)]"
                          : "hover:bg-[var(--hover-tint)]"
                      )}
                    >
                      <td className="px-4 py-2.5 text-[12px] font-medium text-[var(--chat-text)]">{t.name}</td>
                      <td className="px-4 py-2.5 text-[12px] text-[var(--chat-muted)] hidden sm:table-cell max-w-xs truncate">
                        {t.input_preview || "—"}
                      </td>
                      <td className="px-4 py-2.5 text-[12px] font-mono tabular-nums text-[var(--chat-muted)]">
                        {fmtLatency(t.latency)}
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={cn(
                            "inline-block rounded-sm px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                            levelClass(t.level)
                          )}
                        >
                          {t.level}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-[11px] tabular-nums text-[var(--chat-muted)] hidden md:table-cell">
                        {fmtTs(t.timestamp)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </WorkspaceSection>

      {selected && (
        <WorkspaceSection
          title={`Trace Inspector — ${selected.name}`}
          description={`ID: ${selected.id}`}
        >
          <TraceInspector traceId={selected.id} />
        </WorkspaceSection>
      )}
    </WorkspaceShell>
  );
}
