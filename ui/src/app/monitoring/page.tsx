"use client";

import { Activity, RefreshCw } from "lucide-react";
import { NodeStatus } from "@/components/shared/node-status";
import {
  WorkspaceCardGrid,
  WorkspaceLinkCard,
  WorkspaceSection,
  WorkspaceShell,
} from "@/components/workspace/workspace-shell";
import { fetchOpsHealth } from "@/lib/api/ops";
import { fetchGovernanceRequests } from "@/lib/api/workspaces";
import type { ClusterNode, OpsHealth } from "@/types/ops";
import { useCallback, useEffect, useState } from "react";

const CLUSTER_ORDER: Array<{ name: string; role: ClusterNode["role"]; ip: string }> = [
  { name: "Justin-PC", role: "execution", ip: "192.168.2.101" },
  { name: "R730", role: "gateway", ip: "192.168.2.103" },
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
      description="Operations and observability surfaces for the full three-node Hive cluster."
      icon={Activity}
    >
      <WorkspaceSection
        title="Cluster Status Overview"
        description="Justin-PC execution plane, R730 gateway, and control-plane health in one surface."
      >
        <div className="mb-4 flex justify-end">
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {CLUSTER_ORDER.map((cluster) => {
            const node = health?.nodes?.find((n) => n.role === cluster.role || n.name === cluster.name);
            return (
              <div key={cluster.name} className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-[var(--chat-text)]">{cluster.name}</p>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      node?.healthy ? "bg-emerald-950/50 text-emerald-300" : "bg-red-950/50 text-red-300"
                    }`}
                  >
                    {node ? (node.healthy ? "ONLINE" : "DEGRADED") : "UNKNOWN"}
                  </span>
                </div>
                <p className="mt-1 font-mono text-xs text-[var(--chat-muted)]">{cluster.ip}</p>
                <p className="mt-3 text-xs text-[var(--chat-muted)]">Running Containers</p>
                <p className="text-xl font-semibold text-[var(--chat-text)]">{node?.running_count ?? 0}</p>
                {node?.error && <p className="mt-2 text-xs text-red-400">{node.error}</p>}
              </div>
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
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Cluster Containers</p>
            <p className="mt-1 text-xl font-semibold text-[var(--chat-text)]">{health?.running_count ?? 0}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Unhealthy Services</p>
            <p className="mt-1 text-xl font-semibold text-red-400">{unhealthyServices}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Pending Governance</p>
            <p className="mt-1 text-xl font-semibold text-amber-400">{pending}</p>
          </div>
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Inference Nodes - Ollama Status">
        <div className="rounded-2xl border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
          <NodeStatus />
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
