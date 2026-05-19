"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import {
  ackMaintenanceItem,
  fetchMaintenanceAudit,
  fetchMaintenanceQueue,
} from "@/lib/api/maintenance";
import type {
  MaintenanceAuditRow,
  MaintenanceQueueItem,
} from "@/types/maintenance";
import { Button, Card } from "@/components/ui";
import { cn } from "@/lib/utils/cn";

function relativeTime(iso: string) {
  const ms = Date.now() - Date.parse(iso);
  if (Number.isNaN(ms)) return "—";
  const min = Math.floor(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

function severityClass(sev?: string | null) {
  switch ((sev || "").toLowerCase()) {
    case "critical": return "bg-red-500/15 text-red-400";
    case "warning":  return "bg-amber-500/15 text-amber-400";
    default:         return "bg-[var(--chat-panel)] text-[var(--chat-muted)]";
  }
}

function routeClass(route: string) {
  switch (route) {
    case "agent": return "text-emerald-400";
    case "human": return "text-amber-400";
    case "suppressed_cooldown": return "text-sky-400";
    default: return "text-[var(--chat-muted)]";
  }
}

export function MaintenanceQueue() {
  const [items, setItems] = useState<MaintenanceQueueItem[]>([]);
  const [audit, setAudit] = useState<MaintenanceAuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [actor, setActor] = useState("operator");

  async function load() {
    setLoading(true);
    const [queue, recent] = await Promise.all([
      fetchMaintenanceQueue("pending"),
      fetchMaintenanceAudit(50),
    ]);
    setItems(queue);
    setAudit(recent);
    setLoading(false);
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  async function ack(
    id: number,
    status: "acked" | "escalated" | "resolved",
    note?: string
  ) {
    const updated = await ackMaintenanceItem(id, { by: actor, status, note });
    if (updated) {
      setItems((prev) => prev.filter((i) => i.id !== id));
    }
  }

  const counts = useMemo(() => {
    const out = { agent: 0, human: 0, suppressed: 0, unmatched: 0 };
    for (const r of audit) {
      if (r.route === "agent") out.agent += 1;
      else if (r.route === "human") out.human += 1;
      else if (r.route === "suppressed_cooldown") out.suppressed += 1;
      else out.unmatched += 1;
    }
    return out;
  }, [audit]);

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          value={actor}
          onChange={(e) => setActor(e.target.value)}
          placeholder="Your handle"
          className="input-field !py-1.5 text-[12px] w-40"
        />
        <Button
          variant="secondary"
          size="sm"
          onClick={load}
          iconLeft={<RefreshCw size={13} className={loading ? "animate-spin" : ""} />}
        >
          Refresh
        </Button>
        <div className="ml-auto flex flex-wrap items-center gap-3 text-[11px] text-[var(--chat-muted)]">
          <span className="text-[var(--chat-subtle)] uppercase tracking-wider font-semibold text-[10px]">
            Recent dispatches
          </span>
          <DispatchPill label="agent" count={counts.agent} tone="emerald" />
          <DispatchPill label="human" count={counts.human} tone="amber" />
          <DispatchPill label="cooldown" count={counts.suppressed} tone="sky" />
          {counts.unmatched > 0 && (
            <DispatchPill label="unmatched" count={counts.unmatched} tone="muted" />
          )}
        </div>
      </div>

      {/* Pending queue */}
      {items.length === 0 ? (
        <Card padding="lg" className="text-center">
          <CheckCircle2 size={18} className="mx-auto mb-2 text-emerald-400" />
          <p className="text-sm font-medium text-[var(--chat-text)]">Queue is clear</p>
          <p className="mt-1 text-[12px] text-[var(--chat-muted)]">
            Agent-safe alerts handled automatically; nothing awaiting human action.
          </p>
        </Card>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.id}>
              <Card padding="md">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <AlertTriangle size={14} className="text-amber-400 flex-shrink-0" />
                      <span className="font-mono text-[13px] font-medium text-[var(--chat-text)]">
                        {item.alert_name}
                      </span>
                      <span
                        className={cn(
                          "rounded-sm px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                          severityClass(item.severity),
                        )}
                      >
                        {item.severity || "info"}
                      </span>
                      {item.blast_radius && (
                        <span className="rounded-sm bg-[var(--chat-panel)] border border-[var(--chat-border)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-[var(--chat-muted)]">
                          blast: {item.blast_radius}
                        </span>
                      )}
                      <span className="text-[11px] tabular-nums text-[var(--chat-subtle)]">
                        {relativeTime(item.created_at)}
                      </span>
                    </div>
                    {item.summary && (
                      <p className="mt-1.5 text-[13px] text-[var(--chat-text)]">{item.summary}</p>
                    )}
                    {item.description && (
                      <p className="mt-1 text-[12px] text-[var(--chat-muted)] leading-relaxed">
                        {item.description}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {Object.entries(item.alert_labels)
                        .filter(([k]) => k !== "alertname")
                        .slice(0, 8)
                        .map(([k, v]) => (
                          <span
                            key={k}
                            className="rounded-sm font-mono px-1.5 py-0.5 text-[10px] text-[var(--chat-muted)]"
                            style={{
                              background: "var(--chat-bg)",
                              border: "1px solid var(--chat-border)",
                            }}
                          >
                            {k}={v}
                          </span>
                        ))}
                    </div>
                  </div>
                  <div className="flex flex-shrink-0 flex-wrap gap-1.5">
                    {item.runbook && (
                      <a
                        href={item.runbook}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center rounded-sm border border-[var(--chat-accent)]/40 bg-[var(--chat-accent-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--chat-accent)] hover:bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] transition-colors"
                      >
                        Runbook
                      </a>
                    )}
                    <button
                      onClick={() => ack(item.id, "acked")}
                      className="inline-flex items-center rounded-sm border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-400 hover:bg-emerald-500/15 transition-colors"
                    >
                      Ack
                    </button>
                    <button
                      onClick={() => ack(item.id, "resolved", "manually resolved")}
                      className="inline-flex items-center rounded-sm border border-[var(--chat-accent)]/40 bg-[var(--chat-accent-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--chat-accent)] hover:bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] transition-colors"
                    >
                      Resolved
                    </button>
                    <button
                      onClick={() => ack(item.id, "escalated")}
                      className="inline-flex items-center rounded-sm border border-red-500/40 bg-red-500/10 px-2.5 py-1 text-[11px] font-medium text-red-400 hover:bg-red-500/15 transition-colors"
                    >
                      Escalate
                    </button>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {/* Recent dispatches */}
      <div>
        <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">
          Recent dispatches
        </h3>
        <div className="surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr
                  className="border-b border-[var(--chat-border)] text-left"
                  style={{ background: "color-mix(in srgb, var(--chat-panel) 60%, transparent)" }}
                >
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">When</th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">Alert</th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">Route</th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">Action</th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">Queue ID</th>
                </tr>
              </thead>
              <tbody>
                {audit.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-[var(--chat-muted)]">
                      No dispatches yet.
                    </td>
                  </tr>
                ) : (
                  audit.map((row, i) => (
                    <tr
                      key={row.id}
                      className={cn(
                        "transition-colors hover:bg-[var(--hover-tint)]",
                        i !== audit.length - 1 && "border-b border-[var(--divider)]",
                      )}
                    >
                      <td className="px-3 py-2 tabular-nums text-[var(--chat-muted)]">
                        {relativeTime(row.ts)}
                      </td>
                      <td className="px-3 py-2 font-mono text-[var(--chat-text)]">
                        {row.alert_name}
                      </td>
                      <td className={cn("px-3 py-2 font-medium", routeClass(row.route))}>
                        {row.route}
                      </td>
                      <td className="px-3 py-2 text-[var(--chat-muted)]">
                        {row.action || "—"}
                      </td>
                      <td className="px-3 py-2 tabular-nums text-[var(--chat-muted)]">
                        {row.queue_item_id ?? "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function DispatchPill({ label, count, tone }: { label: string; count: number; tone: "emerald" | "amber" | "sky" | "muted" }) {
  const toneClass = {
    emerald: "text-emerald-400 bg-emerald-500/10",
    amber:   "text-amber-400 bg-amber-500/10",
    sky:     "text-sky-400 bg-sky-500/10",
    muted:   "text-[var(--chat-muted)] bg-[var(--chat-panel)]",
  }[tone];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[11px] font-medium", toneClass)}>
      <span>{label}</span>
      <span className="tabular-nums opacity-80">{count}</span>
    </span>
  );
}
