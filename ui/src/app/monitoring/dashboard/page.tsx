"use client";

import { ActivitySquare, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { NodeStatus } from "@/components/shared/node-status";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchOpsHealth } from "@/lib/api/ops";
import type { ClusterNode, OpsHealth } from "@/types/ops";

const REFRESH_MS = 30_000;

function Dot({ healthy }: { healthy: boolean }) {
  return healthy ? (
    <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
      <CheckCircle2 size={12} /> Healthy
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs text-red-400">
      <XCircle size={12} /> Down
    </span>
  );
}

function NodeContainerTable({ node }: { node: ClusterNode }) {
  return (
    <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)]">
      <div className="flex items-center justify-between border-b border-[var(--chat-border)] px-4 py-2.5">
        <div>
          <p className="text-sm font-medium text-[var(--chat-text)]">{node.name}</p>
          <p className="font-mono text-[11px] text-[var(--chat-muted)]">{node.ip} · {node.role}</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold text-[var(--chat-text)]">{node.running_count}</p>
          <p className="text-[11px] text-[var(--chat-muted)]">containers</p>
        </div>
      </div>

      {node.error && <p className="px-4 py-3 text-xs text-red-400">{node.error}</p>}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--chat-border)] bg-[var(--chat-surface)]">
              <th className="px-4 py-2 text-left text-xs font-medium text-[var(--chat-muted)]">Container</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-[var(--chat-muted)]">Image</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-[var(--chat-muted)]">Uptime</th>
            </tr>
          </thead>
          <tbody>
            {node.containers.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-xs text-[var(--chat-muted)]">
                  No containers visible from this node.
                </td>
              </tr>
            ) : (
              node.containers.map((container) => (
                <tr key={`${node.name}-${container.name}`} className="border-b border-[var(--chat-border)] hover:bg-[var(--chat-surface)]">
                  <td className="px-4 py-2 font-mono text-xs text-[var(--chat-text)]">{container.name}</td>
                  <td className="px-4 py-2 font-mono text-xs text-[var(--chat-muted)]">{container.image}</td>
                  <td className="px-4 py-2 text-xs text-[var(--chat-muted)]">{container.uptime}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function MonitoringDashboardPage() {
  const [health, setHealth] = useState<OpsHealth | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    const data = await fetchOpsHealth();
    setHealth(data);
    setRefreshedAt(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  const downServices = useMemo(() => health?.control_plane.filter((s) => !s.healthy) ?? [], [health]);

  return (
    <WorkspaceShell
      title="Monitoring Dashboard"
      description="Cluster-wide infrastructure health for execution, gateway, and control nodes."
      icon={ActivitySquare}
    >
      {downServices.length > 0 && (
        <div className="mb-6 rounded-lg border border-red-800 bg-red-950/40 px-4 py-3">
          <p className="text-sm font-medium text-red-400">
            {downServices.length} service{downServices.length > 1 ? "s" : ""} unreachable: {downServices.map((s) => s.name).join(", ")}
          </p>
        </div>
      )}

      <div className="mb-6 flex items-center justify-between rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-4 py-2.5 text-sm">
        <div className="flex items-center gap-4">
          <span className="text-[var(--chat-muted)]">System</span>
          <span className={health?.status === "ONLINE" ? "font-medium text-emerald-400" : "font-medium text-yellow-400"}>
            {health?.status ?? "-"}
          </span>
          {health && (
            <span className="text-[var(--chat-muted)]">
              {health.running_count} container{health.running_count !== 1 ? "s" : ""} running across cluster
            </span>
          )}
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs text-[var(--chat-muted)] transition-colors hover:text-[var(--chat-text)] disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          {refreshedAt ? `Updated ${refreshedAt.toLocaleTimeString()}` : "Loading..."}
        </button>
      </div>

      <WorkspaceSection title="Cluster Containers" description="Container inventories from Lovelace, Turing, and Control Node.">
        <div className="space-y-3">
          {(health?.nodes ?? []).map((node) => (
            <NodeContainerTable key={node.name} node={node} />
          ))}
          {health && health.nodes.length === 0 && (
            <p className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-4 py-6 text-center text-sm text-[var(--chat-muted)]">
              No cluster nodes reported by backend.
            </p>
          )}
          {!health && (
            <p className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-4 py-6 text-center text-sm text-[var(--chat-muted)]">
              Fetching cluster containers...
            </p>
          )}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Control Plane - Service Health" description="Health checks against Langfuse, PostgreSQL, SPIRE, and MinIO.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {health?.control_plane.map((svc) => (
            <div key={svc.name} className={`rounded-lg border p-3 ${svc.healthy ? "border-[var(--chat-border)] bg-[var(--chat-panel)]" : "border-red-900/60 bg-red-950/30"}`}>
              <p className="text-xs font-medium text-[var(--chat-text)]">{svc.name}</p>
              <p className="mt-0.5 font-mono text-xs text-[var(--chat-muted)]">:{svc.port}</p>
              <div className="mt-2">
                <Dot healthy={svc.healthy} />
              </div>
            </div>
          ))}
          {!health && <div className="col-span-full py-6 text-center text-sm text-[var(--chat-muted)]">Checking control-plane services...</div>}
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
