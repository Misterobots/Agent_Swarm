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

function severityColor(sev?: string | null) {
  switch ((sev || "").toLowerCase()) {
    case "critical":
      return "text-red-400 border-red-900/80 bg-red-950/30";
    case "warning":
      return "text-amber-400 border-amber-900/80 bg-amber-950/30";
    default:
      return "text-[var(--chat-muted)] border-[var(--chat-border)] bg-[var(--chat-panel)]";
  }
}

function routeColor(route: string) {
  switch (route) {
    case "agent":
      return "text-emerald-400";
    case "human":
      return "text-amber-400";
    case "suppressed_cooldown":
      return "text-sky-400";
    default:
      return "text-[var(--chat-muted)]";
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
      <div className="flex flex-wrap items-center gap-3">
        <input
          value={actor}
          onChange={(e) => setActor(e.target.value)}
          placeholder="Your handle"
          className="rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-2.5 py-1.5 text-xs text-[var(--chat-text)]"
        />
        <button
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
        <div className="ml-auto flex flex-wrap items-center gap-3 text-xs text-[var(--chat-muted)]">
          <span>
            Recent dispatches —{" "}
            <span className="text-emerald-400">agent {counts.agent}</span> ·{" "}
            <span className="text-amber-400">human {counts.human}</span> ·{" "}
            <span className="text-sky-400">cooldown {counts.suppressed}</span> ·{" "}
            unmatched {counts.unmatched}
          </span>
        </div>
      </div>

      <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
        {items.length === 0 ? (
          <div className="flex items-center gap-2 px-2 py-6 text-sm text-[var(--chat-muted)]">
            <CheckCircle2 size={16} className="text-emerald-400" />
            Queue is clear. Agent-safe alerts handled automatically; nothing
            awaiting human action.
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <li
                key={item.id}
                className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-surface)] p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <AlertTriangle
                        size={14}
                        className="text-amber-400 shrink-0"
                      />
                      <span className="font-mono text-sm text-[var(--chat-text)]">
                        {item.alert_name}
                      </span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${severityColor(item.severity)}`}
                      >
                        {item.severity || "info"}
                      </span>
                      {item.blast_radius && (
                        <span className="rounded-full border border-[var(--chat-border)] bg-[var(--chat-panel)] px-2 py-0.5 text-[10px] uppercase tracking-wide text-[var(--chat-muted)]">
                          blast: {item.blast_radius}
                        </span>
                      )}
                      <span className="text-[11px] text-[var(--chat-muted)]">
                        {relativeTime(item.created_at)}
                      </span>
                    </div>
                    {item.summary && (
                      <p className="mt-1.5 text-xs text-[var(--chat-text)]">
                        {item.summary}
                      </p>
                    )}
                    {item.description && (
                      <p className="mt-1 text-xs text-[var(--chat-muted)]">
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
                            className="rounded bg-[var(--chat-bg)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--chat-muted)]"
                          >
                            {k}={v}
                          </span>
                        ))}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-1.5">
                    {item.runbook && (
                      <a
                        href={item.runbook}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded border border-[var(--chat-accent)]/40 bg-[var(--chat-accent)]/10 px-2 py-1 text-xs text-[var(--chat-accent)]"
                      >
                        Runbook
                      </a>
                    )}
                    <button
                      onClick={() => ack(item.id, "acked")}
                      className="rounded border border-emerald-800/80 bg-emerald-950/30 px-2 py-1 text-xs text-emerald-400"
                    >
                      Ack
                    </button>
                    <button
                      onClick={() => ack(item.id, "resolved", "manually resolved")}
                      className="rounded border border-[var(--chat-accent)]/40 bg-[var(--chat-accent)]/10 px-2 py-1 text-xs text-[var(--chat-accent)]"
                    >
                      Resolved
                    </button>
                    <button
                      onClick={() => ack(item.id, "escalated")}
                      className="rounded border border-red-900/80 bg-red-950/30 px-2 py-1 text-xs text-red-400"
                    >
                      Escalate
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--chat-muted)]">
          Recent dispatches
        </h3>
        <div className="overflow-x-auto rounded-lg border border-[var(--chat-border)]">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--chat-border)] bg-[var(--chat-surface)] text-left text-[var(--chat-muted)]">
                <th className="px-3 py-2 font-medium">When</th>
                <th className="px-3 py-2 font-medium">Alert</th>
                <th className="px-3 py-2 font-medium">Route</th>
                <th className="px-3 py-2 font-medium">Action</th>
                <th className="px-3 py-2 font-medium">Queue ID</th>
              </tr>
            </thead>
            <tbody>
              {audit.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-3 py-6 text-center text-[var(--chat-muted)]"
                  >
                    No dispatches yet.
                  </td>
                </tr>
              ) : (
                audit.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b border-[var(--chat-border)] hover:bg-[var(--chat-surface)]"
                  >
                    <td className="px-3 py-2 text-[var(--chat-muted)]">
                      {relativeTime(row.ts)}
                    </td>
                    <td className="px-3 py-2 font-mono text-[var(--chat-text)]">
                      {row.alert_name}
                    </td>
                    <td className={`px-3 py-2 ${routeColor(row.route)}`}>
                      {row.route}
                    </td>
                    <td className="px-3 py-2 text-[var(--chat-muted)]">
                      {row.action || "—"}
                    </td>
                    <td className="px-3 py-2 text-[var(--chat-muted)]">
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
  );
}
