"use client";

import { ActivitySquare, AlertTriangle, RefreshCw } from "lucide-react";
import { NodeStatus } from "@/components/shared/node-status";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { Button, Card } from "@/components/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchOpsHealth } from "@/lib/api/ops";
import type { ClusterNode, OpsHealth } from "@/types/ops";
import { cn } from "@/lib/utils/cn";

const REFRESH_MS = 30_000;

function StatusDot({ healthy, label }: { healthy: boolean; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", healthy ? "bg-emerald-400" : "bg-red-400 animate-pulse")} />
      <span className={cn("text-[11px] font-medium", healthy ? "text-emerald-400" : "text-red-400")}>
        {label ?? (healthy ? "Healthy" : "Down")}
      </span>
    </span>
  );
}

function NodeContainerTable({ node }: { node: ClusterNode }) {
  return (
    <div className="surface overflow-hidden">
      <div
        className="flex items-center justify-between px-4 py-3 border-b border-[var(--chat-border)]"
        style={{ background: "color-mix(in srgb, var(--chat-panel) 60%, transparent)" }}
      >
        <div>
          <p className="text-[13px] font-semibold text-[var(--chat-text)] tracking-tight">{node.name}</p>
          <p className="mt-0.5 font-mono text-[11px] text-[var(--chat-subtle)]">{node.ip} · {node.role}</p>
        </div>
        <div className="text-right">
          <p className="text-[20px] font-semibold tabular-nums text-[var(--chat-text)] leading-none">{node.running_count}</p>
          <p className="mt-1 text-[10px] uppercase tracking-wide text-[var(--chat-subtle)]">containers</p>
        </div>
      </div>

      {node.error && (
        <div className="px-4 py-3 text-xs text-red-400 bg-red-500/5 border-b border-[var(--chat-border)]">
          {node.error}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">Container</th>
              <th className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">Image</th>
              <th className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">Uptime</th>
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
              node.containers.map((container, i) => (
                <tr
                  key={`${node.name}-${container.name}`}
                  className={cn(
                    "transition-colors hover:bg-[var(--hover-tint)]",
                    i !== node.containers.length - 1 && "border-b border-[var(--divider)]",
                  )}
                >
                  <td className="px-4 py-2 font-mono text-[12px] text-[var(--chat-text)]">{container.name}</td>
                  <td className="px-4 py-2 font-mono text-[12px] text-[var(--chat-muted)] truncate max-w-xs">{container.image}</td>
                  <td className="px-4 py-2 text-[12px] text-[var(--chat-muted)] tabular-nums">{container.uptime}</td>
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
  const systemOnline = health?.status === "ONLINE";

  return (
    <WorkspaceShell
      title="Monitoring Dashboard"
      description="Cluster-wide infrastructure health for execution, gateway, and control nodes."
      icon={ActivitySquare}
      actions={
        <Button
          variant="secondary"
          size="sm"
          onClick={refresh}
          iconLeft={<RefreshCw size={13} className={loading ? "animate-spin" : ""} />}
        >
          {refreshedAt ? `Updated ${refreshedAt.toLocaleTimeString()}` : "Refresh"}
        </Button>
      }
    >
      {downServices.length > 0 && (
        <div
          className="mb-6 flex items-start gap-3 rounded-md px-4 py-3"
          style={{
            background: "color-mix(in srgb, #f87171 8%, var(--chat-surface))",
            border: "1px solid color-mix(in srgb, #f87171 35%, var(--chat-border))",
            boxShadow: "var(--elev-1)",
          }}
        >
          <AlertTriangle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-red-400">
              {downServices.length} service{downServices.length > 1 ? "s" : ""} unreachable
            </p>
            <p className="mt-0.5 text-[12px] text-[var(--chat-muted)]">
              {downServices.map((s) => s.name).join(", ")}
            </p>
          </div>
        </div>
      )}

      <Card padding="md" className="mb-6">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-[var(--chat-subtle)]">System</span>
            {health ? (
              <StatusDot healthy={systemOnline} label={health.status} />
            ) : (
              <span className="text-[12px] text-[var(--chat-muted)]">—</span>
            )}
            {health && (
              <span className="text-[12px] text-[var(--chat-muted)] tabular-nums">
                {health.running_count} container{health.running_count !== 1 ? "s" : ""} running
              </span>
            )}
          </div>
        </div>
      </Card>

      <WorkspaceSection title="Cluster Containers" description="Container inventories from Lovelace, Turing, and Control Node.">
        <div className="space-y-3">
          {(health?.nodes ?? []).map((node) => (
            <NodeContainerTable key={node.name} node={node} />
          ))}
          {health && health.nodes.length === 0 && (
            <Card padding="lg" className="text-center">
              <p className="text-sm text-[var(--chat-muted)]">No cluster nodes reported by backend.</p>
            </Card>
          )}
          {!health && (
            <Card padding="lg" className="text-center">
              <p className="text-sm text-[var(--chat-muted)]">Fetching cluster containers…</p>
            </Card>
          )}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Control Plane — Service Health" description="Health checks against Langfuse, PostgreSQL, SPIRE, and MinIO.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {health?.control_plane.map((svc) => (
            <Card
              key={svc.name}
              padding="sm"
              style={
                !svc.healthy
                  ? { background: "color-mix(in srgb, #f87171 8%, var(--chat-surface))" }
                  : undefined
              }
              className={cn(!svc.healthy && "!border-red-900/60")}
            >
              <p className="text-[13px] font-medium text-[var(--chat-text)]">{svc.name}</p>
              <p className="mt-0.5 font-mono text-[11px] text-[var(--chat-subtle)]">:{svc.port}</p>
              <div className="mt-2">
                <StatusDot healthy={svc.healthy} />
              </div>
            </Card>
          ))}
          {!health && <div className="col-span-full py-6 text-center text-sm text-[var(--chat-muted)]">Checking control-plane services…</div>}
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
