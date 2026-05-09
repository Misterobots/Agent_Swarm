"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ClipboardCheck,
  Gauge,
  HeartPulse,
  RefreshCw,
  Shield,
  Wrench,
} from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { OpsDashboard } from "@/components/ops/ops-dashboard";
import { MaintenanceQueue } from "@/components/mission-control/maintenance-queue";
import { ServiceHealthBody } from "@/components/monitoring/service-health-body";
import { GovernanceWorkflow } from "@/components/governance/governance-workflow";
import { fetchOpsHealth } from "@/lib/api/ops";
import { fetchGovernanceRequests } from "@/lib/api/workspaces";
import { fetchMaintenanceQueue } from "@/lib/api/maintenance";
import type { OpsHealth } from "@/types/ops";
import type { GovernanceRequest } from "@/types/workspaces";

type TabId = "status" | "action-queue" | "service-health" | "diagnostics";

const TABS: { id: TabId; label: string; icon: typeof Activity }[] = [
  { id: "status", label: "Status", icon: Gauge },
  { id: "action-queue", label: "Action Queue", icon: ClipboardCheck },
  { id: "service-health", label: "Service Health", icon: HeartPulse },
  { id: "diagnostics", label: "Diagnostics", icon: Wrench },
];

const DIAGNOSTIC_RUNBOOKS: { title: string; body: string; cmd: string }[] = [
  {
    title: "Cluster Health Check",
    body: "Validate all three nodes and control-plane service checks.",
    cmd: "GET /api/v1/ops/health",
  },
  {
    title: "Logs Diagnostic",
    body: "Inspect agent-runtime and gateway logs after incidents.",
    cmd: "docker compose logs --tail=200",
  },
  {
    title: "Reliability Suite",
    body: "Run endpoint and host reliability scripts from execution plane.",
    cmd: "bash test_endpoints.sh && bash test_host.sh",
  },
  {
    title: "Node Health Check",
    body: "Validate all inference nodes and loaded model state.",
    cmd: "GET /api/v1/health/nodes",
  },
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
  const actionQueueCount = pendingMaint + pendingGov.length;

  return (
    <WorkspaceShell
      title="Mission Control"
      description="Unified operator surface for status, action queue, service health, and diagnostics."
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
              t.id === "action-queue"
                ? actionQueueCount
                : t.id === "service-health"
                  ? unhealthy.length
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
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[10px] ${
                      t.id === "service-health"
                        ? "bg-red-500/20 text-red-400"
                        : "bg-amber-500/20 text-amber-400"
                    }`}
                  >
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

        {tab === "action-queue" && (
          <div className="space-y-8">
            <section>
              <div className="mb-3 flex items-baseline justify-between">
                <h3 className="text-sm font-medium uppercase tracking-wide text-[var(--chat-muted)]">
                  Maintenance ({pendingMaint})
                </h3>
                <p className="text-xs text-[var(--chat-muted)]">
                  Alerts routed by manifest. Agent-safe items dispatch automatically.
                </p>
              </div>
              <MaintenanceQueue />
            </section>
            <section>
              <div className="mb-3 flex items-baseline justify-between">
                <h3 className="text-sm font-medium uppercase tracking-wide text-[var(--chat-muted)]">
                  Governance ({pendingGov.length})
                </h3>
                <Link
                  href="/governance"
                  className="text-xs text-[var(--chat-accent)] underline-offset-2 hover:underline"
                >
                  Open in dedicated view →
                </Link>
              </div>
              <GovernanceWorkflow />
            </section>
          </div>
        )}

        {tab === "service-health" && <ServiceHealthBody />}

        {tab === "diagnostics" && (
          <div className="space-y-6">
            <p className="text-sm text-[var(--chat-muted)]">
              Common reliability and incident-response references. Copy and run
              from the execution plane.
            </p>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {DIAGNOSTIC_RUNBOOKS.map((card) => (
                <div
                  key={card.title}
                  className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3"
                >
                  <p className="text-sm font-medium text-[var(--chat-text)]">
                    {card.title}
                  </p>
                  <p className="mt-1 text-xs text-[var(--chat-muted)]">
                    {card.body}
                  </p>
                  <code className="mt-2 block rounded bg-[var(--chat-bg)] px-2 py-1 text-xs text-[var(--chat-muted)]">
                    {card.cmd}
                  </code>
                </div>
              ))}
            </div>
            <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--chat-muted)]">
                Related surfaces
              </p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <Link
                  href="/monitoring/dashboard"
                  className="rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] p-2 text-xs hover:border-[var(--chat-accent)]"
                >
                  <p className="text-[var(--chat-text)]">Health Dashboard</p>
                  <p className="mt-0.5 text-[var(--chat-muted)]">Cluster-wide containers</p>
                </Link>
                <Link
                  href="/monitoring/grafana"
                  className="rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] p-2 text-xs hover:border-[var(--chat-accent)]"
                >
                  <p className="text-[var(--chat-text)]">Grafana</p>
                  <p className="mt-0.5 text-[var(--chat-muted)]">Metrics + logs</p>
                </Link>
                <Link
                  href="/monitoring/traces"
                  className="rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] p-2 text-xs hover:border-[var(--chat-accent)]"
                >
                  <p className="text-[var(--chat-text)]">Traces</p>
                  <p className="mt-0.5 text-[var(--chat-muted)]">Request flow</p>
                </Link>
                <Link
                  href="/monitoring/evidence-locker"
                  className="rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] p-2 text-xs hover:border-[var(--chat-accent)]"
                >
                  <p className="text-[var(--chat-text)]">Evidence Locker</p>
                  <p className="mt-0.5 text-[var(--chat-muted)]">Runbook archive</p>
                </Link>
              </div>
            </div>
          </div>
        )}
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
