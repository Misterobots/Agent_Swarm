"use client";

import { ExternalLink, Radar, RefreshCw, Search } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { fetchTraceDetail, fetchTraces } from "@/lib/api/ops";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Observation, Trace, TraceDetail } from "@/types/ops";

// ── helpers ──────────────────────────────────────────────────────────────
function levelColor(level: string) {
  if (level === "ERROR") return "text-red-400 bg-red-950/40 border-red-900/60";
  if (level === "WARNING") return "text-yellow-400 bg-yellow-950/40 border-yellow-900/60";
  return "text-emerald-400 bg-emerald-950/20 border-emerald-900/40";
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
    return ms >= 1000 ? ` (${(ms / 1000).toFixed(2)}s)` : ` (${ms}ms)`;
  } catch {
    return "";
  }
}

// ── sub-components ────────────────────────────────────────────────────────
function ObservationRow({ obs }: { obs: Observation }) {
  const [open, setOpen] = useState(false);
  const icon = obs.level === "ERROR" ? "🔴" : "🟢";
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
    <div className="rounded-lg border border-[var(--chat-border)] text-sm">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-2 px-3 py-2.5 text-left hover:bg-[var(--chat-surface)]"
      >
        <span className="mt-0.5 shrink-0">{icon}</span>
        <span className="flex-1 text-xs text-[var(--chat-text)]">
          <span className="font-mono text-[var(--chat-muted)] mr-1.5">[{obs.type?.toUpperCase()}]</span>
          {obs.name}
          {duration && <span className="text-[var(--chat-muted)]">{duration}</span>}
          {obs.model && (
            <span className="ml-2 font-mono text-xs text-[var(--chat-accent)]">· {obs.model}</span>
          )}
          {tok && <span className="ml-2 text-[var(--chat-muted)]">· {tok}</span>}
        </span>
      </button>

      {open && (
        <div className="border-t border-[var(--chat-border)] px-3 py-3 space-y-3">
          {obs.input != null && (
            <div>
              <p className="mb-1 text-xs font-medium text-[var(--chat-muted)]">Input / Prompt</p>
              <pre className="overflow-x-auto rounded bg-[var(--chat-bg)] px-3 py-2 text-xs text-[var(--chat-text)] whitespace-pre-wrap max-h-48">
                {typeof obs.input === "string"
                  ? obs.input
                  : JSON.stringify(obs.input, null, 2)}
              </pre>
            </div>
          )}
          {obs.output != null && (
            <div>
              <p className="mb-1 text-xs font-medium text-[var(--chat-muted)]">Output / Response</p>
              <pre className="overflow-x-auto rounded bg-[var(--chat-bg)] px-3 py-2 text-xs text-[var(--chat-text)] whitespace-pre-wrap max-h-48">
                {typeof obs.output === "string"
                  ? obs.output
                  : JSON.stringify(obs.output, null, 2)}
              </pre>
            </div>
          )}
          {obs.metadata != null && (
            <div>
              <p className="mb-1 text-xs font-medium text-[var(--chat-muted)]">Metadata</p>
              <pre className="overflow-x-auto rounded bg-[var(--chat-bg)] px-3 py-2 text-xs text-[var(--chat-muted)] whitespace-pre-wrap max-h-32">
                {JSON.stringify(obs.metadata, null, 2)}
              </pre>
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
    return <p className="py-6 text-center text-sm text-[var(--chat-muted)]">Loading trace detail…</p>;
  }
  if (!detail) {
    return <p className="py-6 text-center text-sm text-red-400">Failed to load trace detail.</p>;
  }

  const { trace, observations } = detail;

  return (
    <div className="space-y-4">
      {/* Trace metadata card */}
      <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-4 py-3">
        <div className="flex items-start justify-between gap-4">
          <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs sm:grid-cols-4">
            <span className="text-[var(--chat-muted)]">Name</span>
            <span className="col-span-1 text-[var(--chat-text)] font-medium">
              {String(trace.name ?? "—")}
            </span>
            <span className="text-[var(--chat-muted)]">Status</span>
            <span className="col-span-1 text-[var(--chat-text)]">{String(trace.level ?? "DEFAULT")}</span>
            <span className="text-[var(--chat-muted)]">Latency</span>
            <span className="col-span-1 text-[var(--chat-text)]">
              {fmtLatency(typeof trace.latency === "number" ? trace.latency : null)}
            </span>
            <span className="text-[var(--chat-muted)]">Timestamp</span>
            <span className="col-span-1 text-[var(--chat-text)]">
              {fmtTs(typeof trace.timestamp === "string" ? trace.timestamp : null)}
            </span>
          </div>
          {(langfuseUrl ?? detail.langfuse_url) && (
            <a
              href={langfuseUrl ?? detail.langfuse_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex shrink-0 items-center gap-1 text-xs text-[var(--chat-accent)] hover:text-[var(--chat-accent-strong)]"
            >
              Langfuse <ExternalLink size={12} />
            </a>
          )}
        </div>
        {trace.input != null && (
          <div className="mt-3 border-t border-[var(--chat-border)] pt-3">
            <p className="mb-1 text-xs font-medium text-[var(--chat-muted)]">Root Input</p>
            <pre className="overflow-x-auto rounded bg-[var(--chat-bg)] px-3 py-2 text-xs text-[var(--chat-text)] whitespace-pre-wrap max-h-32">
              {typeof trace.input === "string"
                ? trace.input
                : JSON.stringify(trace.input, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Observations */}
      <div>
        <p className="mb-2 text-xs font-medium text-[var(--chat-muted)]">
          Observations ({observations.length} span{observations.length !== 1 ? "s" : ""})
        </p>
        {observations.length === 0 ? (
          <p className="text-xs text-[var(--chat-muted)]">No observations recorded for this trace.</p>
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
    >
      {/* Toolbar */}
      <div className="mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--chat-muted)] pointer-events-none"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by trace name, ID, or content…"
            className="w-full rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] py-2 pl-8 pr-3 text-sm text-[var(--chat-text)] placeholder:text-[var(--chat-muted)] focus:border-[var(--chat-accent)] focus:outline-none"
          />
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] transition-colors hover:text-[var(--chat-text)] disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-yellow-900/60 bg-yellow-950/30 px-4 py-2.5 text-sm text-yellow-400">
          {error}
        </div>
      )}

      {/* Trace list */}
      <WorkspaceSection
        title={`Trace Feed${filtered.length !== traces.length ? ` — ${filtered.length} of ${traces.length}` : ` — ${traces.length} traces`}`}
      >
        <div className="overflow-x-auto rounded-lg border border-[var(--chat-border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--chat-border)] bg-[var(--chat-surface)]">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">
                  Agent / Name
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)] hidden sm:table-cell">
                  Input Preview
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)] w-24">
                  Latency
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)] w-20">
                  Level
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)] w-32 hidden md:table-cell">
                  Timestamp
                </th>
              </tr>
            </thead>
            <tbody>
              {loading && traces.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-[var(--chat-muted)]">
                    Loading traces…
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-[var(--chat-muted)]">
                    {error
                      ? "Langfuse unreachable — check LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY."
                      : "No traces match your filter."}
                  </td>
                </tr>
              ) : (
                filtered.map((t) => (
                  <tr
                    key={t.id}
                    onClick={() => setSelected(selected?.id === t.id ? null : t)}
                    className={`cursor-pointer border-b border-[var(--chat-border)] transition-colors ${
                      selected?.id === t.id
                        ? "bg-[var(--chat-surface)]"
                        : "hover:bg-[var(--chat-surface)]"
                    }`}
                  >
                    <td className="px-4 py-2.5 text-xs font-medium text-[var(--chat-text)]">{t.name}</td>
                    <td className="px-4 py-2.5 text-xs text-[var(--chat-muted)] hidden sm:table-cell max-w-xs truncate">
                      {t.input_preview || "—"}
                    </td>
                    <td className="px-4 py-2.5 text-xs font-mono text-[var(--chat-muted)]">
                      {fmtLatency(t.latency)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-block rounded border px-1.5 py-0.5 text-xs ${levelColor(t.level)}`}
                      >
                        {t.level}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-[var(--chat-muted)] hidden md:table-cell">
                      {fmtTs(t.timestamp)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </WorkspaceSection>

      {/* Trace inspector */}
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
