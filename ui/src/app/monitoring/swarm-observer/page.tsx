"use client";

import { Boxes, ChevronDown, Cpu, ExternalLink, Radar, RefreshCw, Search } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { Button, Card } from "@/components/ui";
import { fetchSwarmSessions, fetchTraceDetail, fetchTraces } from "@/lib/api/ops";
import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  Observation,
  SwarmSession,
  SwarmSessionsResponse,
  SwarmWorker,
  Trace,
  TraceDetail,
} from "@/types/ops";
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

function fmtElapsed(s: number | null) {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s % 60)}s`;
}

function workerStateClass(state: SwarmWorker["state"]) {
  switch (state) {
    case "running":
      return "bg-amber-500/15 text-amber-400";
    case "completed":
      return "bg-emerald-500/15 text-emerald-400";
    case "failed":
      return "bg-red-500/15 text-red-400";
    case "cancelled":
      return "bg-zinc-500/15 text-zinc-400";
    default:
      return "bg-[var(--hover-tint)] text-[var(--chat-subtle)]"; // pending
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

// ── trace sub-components ───────────────────────────────────────────────────
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

function MetaField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">{label}</span>
      <span className="text-[var(--chat-text)] font-medium">{children}</span>
    </>
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

// ── Live Agents panel ──────────────────────────────────────────────────────
function WorkerRow({ w }: { w: SwarmWorker }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-[var(--hover-tint)]">
      <span
        className={cn(
          "h-2 w-2 shrink-0 rounded-full",
          w.state === "running" ? "bg-amber-400 animate-pulse" : w.state === "completed" ? "bg-emerald-400" : w.state === "failed" ? "bg-red-400" : "bg-[var(--chat-subtle)]"
        )}
      />
      <span className="w-28 shrink-0 truncate font-medium text-[var(--chat-text)]">{w.name || w.worker_id}</span>
      <span className="w-24 shrink-0 truncate text-[12px] text-[var(--chat-subtle)]">{w.role}</span>
      <span className="hidden w-32 shrink-0 truncate font-mono text-[11px] text-[var(--chat-accent)] md:inline">
        {w.model || "—"}
      </span>
      <span className="flex-1 truncate text-[12px] text-[var(--chat-muted)]">{w.phase}</span>
      <span className="w-16 shrink-0 text-right text-[11px] tabular-nums text-[var(--chat-muted)]">
        {fmtElapsed(w.elapsed_s)}
      </span>
      <span
        className={cn(
          "w-20 shrink-0 rounded-sm px-1.5 py-0.5 text-center text-[10px] font-semibold uppercase tracking-wider",
          workerStateClass(w.state)
        )}
      >
        {w.state}
      </span>
    </div>
  );
}

function SessionCard({ s }: { s: SwarmSession }) {
  return (
    <div className="rounded-lg border border-[var(--chat-border)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--chat-border)] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Boxes size={15} className="text-[var(--chat-subtle)]" />
          <span className="text-sm font-semibold text-[var(--chat-text)]">{s.session_id}</span>
          <span className="font-mono text-[11px] text-[var(--chat-subtle)]">{s.coordination_id}</span>
          {s.owner_id && (
            <span className="rounded bg-[var(--hover-tint)] px-1.5 py-0.5 text-[10px] text-[var(--chat-subtle)]">
              {s.owner_id}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-[var(--chat-subtle)]">
          <span className="flex items-center gap-1 text-amber-400">
            <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
            {s.running_count} running
          </span>
          <span>
            {s.worker_count} worker{s.worker_count !== 1 ? "s" : ""}
          </span>
          <span className="tabular-nums">{fmtElapsed(s.elapsed_s)}</span>
        </div>
      </div>
      {s.workers.length ? (
        <div className="divide-y divide-[var(--chat-border)]">
          {s.workers.map((w) => (
            <WorkerRow key={w.worker_id} w={w} />
          ))}
        </div>
      ) : (
        <div className="px-4 py-3 text-[13px] text-[var(--chat-subtle)]">
          Decomposing — no workers spawned yet.
        </div>
      )}
    </div>
  );
}

function LiveAgentsPanel({ refreshTick }: { refreshTick: number }) {
  const [data, setData] = useState<SwarmSessionsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const d = await fetchSwarmSessions();
    setData(d);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load, refreshTick]);

  const sessions = data?.sessions ?? [];

  return (
    <WorkspaceSection
      title={`Active Coordinations${sessions.length ? ` — ${sessions.length}` : ""}`}
      description="Live swarm sessions and their workers. Polls every 3s. A session disappears when its coordination finishes."
    >
      {data?.error && (
        <div className="mb-3 rounded-md border border-red-700/40 bg-red-950/40 px-4 py-2.5 text-[13px] text-red-300">
          {data.error}
        </div>
      )}
      {loading && !data ? (
        <Card padding="lg" className="text-center">
          <p className="text-sm text-[var(--chat-muted)]">Loading active sessions…</p>
        </Card>
      ) : sessions.length === 0 ? (
        <Card padding="lg" className="text-center">
          <Cpu size={22} className="mx-auto mb-2 text-[var(--chat-subtle)]" />
          <p className="text-sm text-[var(--chat-text)]">No active coordinations.</p>
          <p className="mt-1 text-[12px] text-[var(--chat-muted)]">
            Start a <span className="font-mono text-[var(--chat-accent)]">/swarm</span> task to watch agents here live.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {sessions.map((s) => (
            <SessionCard key={s.coordination_id} s={s} />
          ))}
        </div>
      )}
    </WorkspaceSection>
  );
}

// ── Traces panel (Langfuse) ─────────────────────────────────────────────────
function TracesPanel({ refreshTick }: { refreshTick: number }) {
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
  }, [load, refreshTick]);

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
    <>
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
    </>
  );
}

// ── page ─────────────────────────────────────────────────────────────────
type View = "agents" | "traces";

export default function SwarmObserverPage() {
  const [view, setView] = useState<View>("agents");
  const [refreshTick, setRefreshTick] = useState(0);

  const TABS: { id: View; label: string; icon: typeof Radar }[] = [
    { id: "agents", label: "Live Agents", icon: Boxes },
    { id: "traces", label: "Traces", icon: Radar },
  ];

  return (
    <WorkspaceShell
      title="Swarm Observer"
      description="Live agent sessions and Langfuse trace history for the swarm."
      icon={Radar}
      actions={
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setRefreshTick((t) => t + 1)}
          iconLeft={<RefreshCw size={13} />}
        >
          Refresh
        </Button>
      }
    >
      <div
        role="tablist"
        aria-label="Swarm Observer views"
        className="mb-5 inline-flex items-center gap-1 rounded-md border border-[var(--chat-border)] bg-[var(--chat-panel)] p-1"
        style={{ boxShadow: "var(--elev-1), inset 0 1px 2px rgba(0,0,0,0.08)" }}
      >
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = view === t.id;
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={active}
              onClick={() => setView(t.id)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-[13px] font-medium transition-all",
                active
                  ? "bg-[var(--chat-elevated)] text-[var(--chat-text)] shadow-[var(--elev-1)]"
                  : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
              )}
            >
              <Icon size={14} className={active ? "text-[var(--chat-accent)]" : ""} />
              {t.label}
            </button>
          );
        })}
      </div>

      {view === "agents" ? (
        <LiveAgentsPanel refreshTick={refreshTick} />
      ) : (
        <TracesPanel refreshTick={refreshTick} />
      )}
    </WorkspaceShell>
  );
}
