"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ClipboardCheck,
  Gauge,
  Gavel,
  RefreshCw,
  Shield,
} from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { OpsDashboard } from "@/components/ops/ops-dashboard";
import { MaintenanceQueue } from "@/components/mission-control/maintenance-queue";
import { fetchOpsHealth } from "@/lib/api/ops";
import { fetchGovernanceRequests } from "@/lib/api/workspaces";
import { fetchMaintenanceQueue } from "@/lib/api/maintenance";
import type { OpsHealth } from "@/types/ops";
import type { GovernanceRequest } from "@/types/workspaces";

type TabId = "status" | "maintenance" | "service-health" | "governance";

const TABS: { id: TabId; label: string; icon: typeof Activity }[] = [
  { id: "status", label: "Status", icon: Gauge },
  { id: "maintenance", label: "Maintenance Queue", icon: ClipboardCheck },
  { id: "service-health", label: "Service Checks", icon: Activity },
  { id: "governance", label: "Governance", icon: Gavel },
];

export default function MissionControlPage() {
  const [tab, setTab] = useState<TabId>("status");
  const [health, setHealth] = useState<OpsHealth | null>(null);
  const [requests, setRequests] = useState<GovernanceRequest[]>([]);
  const [pendingMaint, setPendingMaint] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [healthData, reqs, maint] = await Promise.all([
      fetchOpsHealth(),
      fetchGovernanceRequests(),
      fetchMaintenanceQueue("pending", 200),
    ]);
    setHealth(healthData);
    setRequests(reqs);
    setPendingMaint(maint.length);
    setLoading(false);
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const pendingGov = useMemo(
    () =>
      requests.filter(
        (r) => r.status === "PENDING" || r.status === "ASSESSING"
      ),
    [requests]
  );
  const unhealthy = health?.control_plane.filter((s) => !s.healthy) ?? [];

  return (
    <WorkspaceShell
      title="Mission Control"
      description="Unified surface for status, maintenance queue, service checks, and governance approvals."
      icon={Shield}
    >
      <WorkspaceSection title="At a glance">
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Pending Maintenance</p>
            <p className="mt-1 text-xl font-semibold text-amber-400">
              {pendingMaint}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Pending Approvals</p>
            <p className="mt-1 text-xl font-semibold text-amber-400">
              {pendingGov.length}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Unhealthy Services</p>
            <p className="mt-1 text-xl font-semibold text-red-400">
              {unhealthy.length}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Cluster Containers</p>
            <p className="mt-1 text-xl font-semibold text-[var(--chat-text)]">
              {health?.running_count ?? 0}
            </p>
          </div>
        </div>
        <div className="mt-3 flex justify-end">
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Workspaces">
        <div className="mb-4 flex flex-wrap gap-2 border-b border-[var(--chat-border)] pb-2">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            const badge =
              t.id === "maintenance"
                ? pendingMaint
                : t.id === "governance"
                  ? pendingGov.length
                  : null;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`inline-flex items-center gap-1.5 rounded-t-md border-b-2 px-3 py-2 text-sm transition-colors ${
                  active
                    ? "border-[var(--chat-accent)] text-[var(--chat-accent)]"
                    : "border-transparent text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
                }`}
              >
                <Icon size={14} />
                {t.label}
                {badge !== null && badge > 0 && (
                  <span className="rounded-full bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-400">
                    {badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {tab === "status" && (
          <div className="space-y-6">
            <OpsDashboard />
            <div className="grid gap-3 md:grid-cols-3">
              {(health?.nodes ?? []).map((node) => (
                <div
                  key={node.name}
                  className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4"
                >
                  <p className="text-sm font-medium text-[var(--chat-text)]">
                    {node.name}
                  </p>
                  <p className="mt-0.5 font-mono text-xs text-[var(--chat-muted)]">
                    {node.ip}
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--chat-text)]">
                    {node.running_count}
                  </p>
                  <p className="text-xs text-[var(--chat-muted)]">
                    running containers
                  </p>
                </div>
              ))}
            </div>
            <div>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--chat-muted)]">
                Control plane
              </h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                {health?.control_plane.map((svc) => (
                  <div
                    key={svc.name}
                    className={`rounded-lg border p-3 ${svc.healthy ? "border-[var(--chat-border)] bg-[var(--chat-panel)]" : "border-red-900/60 bg-red-950/30"}`}
                  >
                    <p className="text-xs font-medium text-[var(--chat-text)]">
                      {svc.name}
                    </p>
                    <p className="mt-0.5 font-mono text-xs text-[var(--chat-muted)]">
                      :{svc.port}
                    </p>
                    <p
                      className={`mt-2 text-xs ${svc.healthy ? "text-emerald-400" : "text-red-400"}`}
                    >
                      {svc.healthy ? "Healthy" : "Down"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === "maintenance" && <MaintenanceQueue />}

        {tab === "service-health" && (
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4 text-sm text-[var(--chat-muted)]">
            <p>
              The full service-checks surface lives at{" "}
              <Link
                href="/monitoring/service-health"
                className="text-[var(--chat-accent)] underline-offset-2 hover:underline"
              >
                /monitoring/service-health
              </Link>
              . Open it for the canonical view; this tab is the entry point
              from Mission Control.
            </p>
          </div>
        )}

        {tab === "governance" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm text-[var(--chat-muted)]">
                {pendingGov.length} pending request
                {pendingGov.length === 1 ? "" : "s"}.
              </p>
              <Link
                href="/governance"
                className="text-xs text-[var(--chat-accent)] underline-offset-2 hover:underline"
              >
                Open full governance workflow →
              </Link>
            </div>
            <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
              {pendingGov.length === 0 ? (
                <p className="text-sm text-[var(--chat-muted)]">
                  No pending requests.
                </p>
              ) : (
                <ul className="space-y-2">
                  {pendingGov.slice(0, 8).map((req) => (
                    <li
                      key={req.id}
                      className="rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] p-2.5"
                    >
                      <p className="text-xs text-[var(--chat-text)]">
                        <span className="font-mono text-[var(--chat-muted)]">
                          {req.id}
                        </span>{" "}
                        · {req.type} · {req.status}
                      </p>
                      <p className="mt-1 text-xs text-[var(--chat-muted)]">
                        {req.description}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
