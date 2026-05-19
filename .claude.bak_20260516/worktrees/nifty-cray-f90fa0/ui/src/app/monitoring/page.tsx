"use client";

import { Activity, Boxes, RefreshCw, ShieldAlert, ClipboardCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { NodeStatus } from "@/components/shared/node-status";
import {
  WorkspaceCardGrid,
  WorkspaceLinkCard,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";
import { Button, Card } from "@/components/ui";
import { fetchOpsHealth } from "@/lib/api/ops";
import { fetchGovernanceRequests } from "@/lib/api/workspaces";
import type { ClusterNode, OpsHealth } from "@/types/ops";
import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";

const CLUSTER_ORDER: Array<{ name: string; role: ClusterNode["role"]; ip: string }> = [
  { name: "Lovelace", role: "execution", ip: "192.168.2.101" },
  { name: "Turing", role: "gateway", ip: "192.168.2.103" },
  { name: "Control Node", role: "control", ip: "192.168.2.102" },
];

export default function MonitoringPage() {
  const [health, setHealth] = useState<OpsHealth | null>(null);
  const [pending, setPending] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [healthData, requests] = await Promise.all([fetchOpsHealth(), fetchGovernanceRequests()]);
      setHealth(healthData);
      setPending(requests.filter((r) => r.status === "PENDING" || r.status === "ASSESSING").length);
    } catch (err) {
      console.error("[Monitoring] Failed to load health data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const unhealthyServices = health?.control_plane.filter((svc) => !svc.healthy).length ?? 0;

  return (
    <WorkspaceShell
      title="Monitoring"
      description="Operations and observability surfaces for the full three-node Memex cluster."
      icon={Activity}
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
      <WorkspaceSection
        title="Cluster Status Overview"
        description="Lovelace execution plane, Turing gateway, and control-plane health in one surface."
      >
        <div className="grid gap-3 md:grid-cols-3">
          {CLUSTER_ORDER.map((cluster) => {
            const node = health?.nodes?.find((n) => n.role === cluster.role || n.name === cluster.name);
            const status = node ? (node.healthy ? "online" : "degraded") : "unknown";
            return (
              <Card key={cluster.name} padding="md">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-[var(--chat-text)]">{cluster.name}</p>
                  <StatusPill status={status} />
                </div>
                <p className="mt-0.5 font-mono text-[11px] text-[var(--chat-subtle)]">{cluster.ip}</p>
                <p className="mt-3 text-[10px] uppercase tracking-wide font-medium text-[var(--chat-subtle)]">Running Containers</p>
                <p className="mt-1 text-[28px] font-semibold tabular-nums text-[var(--chat-text)] leading-none">
                  {node?.running_count ?? 0}
                </p>
                {node?.error && <p className="mt-2 text-xs text-red-400">{node.error}</p>}
              </Card>
            );
          })}
        </div>
      </WorkspaceSection>

      <WorkspaceSection
        title="Monitoring Surfaces"
        description="These routes provide operational depth beyond top-level cluster health."
      >
        <WorkspaceCardGrid>
          <WorkspaceLinkCard
            title="Dashboard"
            description="Per-node container tables and control-plane service checks."
            href="/monitoring/dashboard"
          />
          <WorkspaceLinkCard
            title="Swarm Observer"
            description="Trace feed and Langfuse inspection for agent activity."
            href="/monitoring/swarm-observer"
          />
          <WorkspaceLinkCard
            title="Evidence Locker"
            description="Browse evidence, architecture notes, and operational artifacts."
            href="/monitoring/evidence-locker"
          />
          <WorkspaceLinkCard
            title="Control Room"
            description="Maintenance queue and reliability command references."
            href="/monitoring/control-room"
          />
        </WorkspaceCardGrid>
      </WorkspaceSection>

      <WorkspaceSection title="Operational Snapshot">
        <div className="grid gap-3 sm:grid-cols-3">
          <Snap label="Cluster Containers" value={health?.running_count ?? 0} icon={Boxes} />
          <Snap label="Unhealthy Services" value={unhealthyServices} icon={ShieldAlert} tone={unhealthyServices > 0 ? "danger" : "neutral"} />
          <Snap label="Pending Governance" value={pending} icon={ClipboardCheck} tone={pending > 0 ? "warning" : "neutral"} />
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Inference Nodes — Ollama Status">
        <Card padding="md">
          <NodeStatus />
        </Card>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}

function StatusPill({ status }: { status: "online" | "degraded" | "unknown" }) {
  const config = {
    online:   { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "Online" },
    degraded: { bg: "bg-red-500/15",     text: "text-red-400",     label: "Degraded" },
    unknown:  { bg: "bg-[var(--chat-panel)]", text: "text-[var(--chat-muted)]", label: "Unknown" },
  }[status];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider", config.bg, config.text)}>
      <span className={cn("w-1 h-1 rounded-full", status === "online" ? "bg-emerald-400" : status === "degraded" ? "bg-red-400 animate-pulse" : "bg-[var(--chat-muted)]")} />
      {config.label}
    </span>
  );
}

function Snap({
  label,
  value,
  icon: Icon,
  tone = "neutral",
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  tone?: "neutral" | "warning" | "danger";
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
