"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Boxes,
  ClipboardCheck,
  Gauge,
  HeartPulse,
  RefreshCw,
  ShieldAlert,
  Shield,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
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
import { Button, Card } from "@/components/ui";
import { cn } from "@/lib/utils/cn";

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

const RELATED_SURFACES: { title: string; subtitle: string; href: string }[] = [
  { title: "Health Dashboard", subtitle: "Cluster-wide containers", href: "/monitoring/dashboard" },
  { title: "Grafana",          subtitle: "Metrics + logs",         href: "/monitoring/grafana"   },
  { title: "Traces",           subtitle: "Request flow",           href: "/monitoring/traces"    },
  { title: "Evidence Locker",  subtitle: "Runbook archive",        href: "/monitoring/evidence-locker" },
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
      <WorkspaceSection title="At a glance">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Pending Maintenance"
            value={pendingMaint}
            icon={Wrench}
            tone={pendingMaint > 0 ? "warning" : "neutral"}
          />
          <StatTile
            label="Pending Approvals"
            value={pendingGov.length}
            icon={ClipboardCheck}
            tone={pendingGov.length > 0 ? "warning" : "neutral"}
          />
          <StatTile
            label="Unhealthy Services"
            value={unhealthy.length}
            icon={unhealthy.length > 0 ? ShieldAlert : Shield}
            tone={unhealthy.length > 0 ? "danger" : "neutral"}
          />
          <StatTile
            label="Cluster Containers"
            value={health?.running_count ?? 0}
            icon={Boxes}
            tone="neutral"
          />
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Workspaces">
        {/* Segmented tab control */}
        <div
          role="tablist"
          aria-label="Mission Control sections"
          className="mb-5 inline-flex items-center gap-1 p-1 rounded-md border border-[var(--chat-border)] bg-[var(--chat-panel)]"
          style={{ boxShadow: "var(--elev-1), inset 0 1px 2px rgba(0,0,0,0.08)" }}
        >
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
                role="tab"
                aria-selected={active}
                onClick={() => setTab(t.id)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-[13px] font-medium transition-all",
                  active
                    ? "bg-[var(--chat-elevated)] text-[var(--chat-text)] shadow-[var(--elev-1)]"
                    : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
                )}
              >
                <Icon size={14} className={active ? "text-[var(--chat-accent)]" : ""} />
                {t.label}
                {badge !== null && badge > 0 && (
                  <span
                    className={cn(
                      "rounded-full px-1.5 text-[10px] font-semibold tabular-nums",
                      t.id === "service-health"
                        ? "bg-red-500/15 text-red-400"
                        : "bg-amber-500/15 text-amber-400"
                    )}
                  >
                    {badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {tab === "status" && <OpsDashboard />}

        {tab === "action-queue" && (
          <div className="space-y-8">
            <section>
              <div className="mb-3 flex items-baseline justify-between gap-3">
                <SubsectionTitle as="h3">
                  Maintenance <span className="ml-1 tabular-nums text-[var(--chat-muted)]">({pendingMaint})</span>
                </SubsectionTitle>
                <p className="text-[12px] text-[var(--chat-muted)]">
                  Alerts routed by manifest. Agent-safe items dispatch automatically.
                </p>
              </div>
              <MaintenanceQueue />
            </section>
            <section>
              <div className="mb-3 flex items-baseline justify-between gap-3">
                <SubsectionTitle as="h3">
                  Governance <span className="ml-1 tabular-nums text-[var(--chat-muted)]">({pendingGov.length})</span>
                </SubsectionTitle>
                <Link
                  href="/governance"
                  className="text-[12px] text-[var(--chat-accent)] underline-offset-4 hover:underline"
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
            <p className="text-[13px] text-[var(--chat-muted)]">
              Common reliability and incident-response references. Copy and run from the execution plane.
            </p>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {DIAGNOSTIC_RUNBOOKS.map((card) => (
                <Card key={card.title} padding="md">
                  <p className="text-[13px] font-semibold text-[var(--chat-text)]">{card.title}</p>
                  <p className="mt-1 text-[12px] leading-relaxed text-[var(--chat-muted)]">{card.body}</p>
                  <code
                    className="mt-3 block rounded-sm px-2.5 py-1.5 text-[11px] font-mono text-[var(--chat-text)]"
                    style={{
                      background: "var(--chat-bg)",
                      border: "1px solid var(--chat-border)",
                      boxShadow: "inset 0 1px 2px rgba(0,0,0,0.15)",
                    }}
                  >
                    {card.cmd}
                  </code>
                </Card>
              ))}
            </div>
            <Card padding="md">
              <SubsectionTitle as="h3">Related surfaces</SubsectionTitle>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {RELATED_SURFACES.map((s) => (
                  <Link
                    key={s.href}
                    href={s.href}
                    className="lift group block rounded-md p-3 transition-colors"
                    style={{
                      background: "var(--chat-panel)",
                      border: "1px solid var(--chat-border)",
                    }}
                  >
                    <p className="text-[13px] font-medium text-[var(--chat-text)] group-hover:text-[var(--chat-accent-strong)] transition-colors">
                      {s.title}
                    </p>
                    <p className="mt-0.5 text-[11px] text-[var(--chat-muted)]">{s.subtitle}</p>
                  </Link>
                ))}
              </div>
            </Card>
          </div>
        )}
      </WorkspaceSection>
    </WorkspaceShell>
  );
}

function StatTile({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  tone: "neutral" | "warning" | "danger";
}) {
  const valueClass = {
    neutral: "text-[var(--chat-text)]",
    warning: "text-amber-400",
    danger:  "text-red-400",
  }[tone];
  const iconClass = {
    neutral: "text-[var(--chat-muted)]",
    warning: "text-amber-400",
    danger:  "text-red-400",
  }[tone];
  return (
    <Card padding="md">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--chat-subtle)]">{label}</p>
        <Icon size={15} className={iconClass} />
      </div>
      <p className={cn("mt-2 text-[28px] font-semibold tabular-nums leading-none", valueClass)}>
        {value}
      </p>
    </Card>
  );
}

function SubsectionTitle({
  children,
  as = "h3",
}: {
  children: React.ReactNode;
  as?: "h2" | "h3";
}) {
  const Tag = as as React.ElementType;
  return (
    <Tag className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">
      {children}
    </Tag>
  );
}
