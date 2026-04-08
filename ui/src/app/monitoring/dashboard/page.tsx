"use client";

import { ActivitySquare, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { NodeStatus } from "@/components/shared/node-status";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { useCallback, useEffect, useState } from "react";
import { fetchOpsHealth } from "@/lib/api/ops";
import type { OpsHealth } from "@/types/ops";

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

  const downServices = health?.control_plane.filter((s) => !s.healthy) ?? [];

  return (
    <WorkspaceShell
      title="Monitoring Dashboard"
      description="Real-time infrastructure health — containers, control-plane services, and inference nodes."
      icon={ActivitySquare}
    >
      {downServices.length > 0 && (
        <div className="mb-6 rounded-lg border border-red-800 bg-red-950/40 px-4 py-3">
          <p className="text-sm font-medium text-red-400">
            {downServices.length} service{downServices.length > 1 ? "s" : ""} unreachable:{" "}
            {downServices.map((s) => s.name).join(", ")}
          </p>
        </div>
      )}

      {/* Status bar */}
      <div className="mb-6 flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-2.5 text-sm">
        <div className="flex items-center gap-4">
          <span className="text-zinc-400">System</span>
          <span
            className={
              health?.status === "ONLINE"
                ? "font-medium text-emerald-400"
                : "font-medium text-yellow-400"
            }
          >
            {health?.status ?? "—"}
          </span>
          {health && (
            <span className="text-zinc-500">
              {health.running_count} container{health.running_count !== 1 ? "s" : ""} running
            </span>
          )}
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300 disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          {refreshedAt ? `Updated ${refreshedAt.toLocaleTimeString()}` : "Loading…"}
        </button>
      </div>

      {/* Execution plane table */}
      <WorkspaceSection
        title="Execution Plane — Running Containers"
        description="Live container list via Docker socket. Refreshes every 30s."
      >
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/80">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">
                  Container
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">Image</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">Uptime</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading && !health ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-zinc-500">
                    Fetching containers…
                  </td>
                </tr>
              ) : !health || health.execution_plane.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-zinc-500">
                    No containers detected (Docker socket may be unavailable in this environment)
                  </td>
                </tr>
              ) : (
                health.execution_plane.map((c) => (
                  <tr
                    key={c.name}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30"
                  >
                    <td className="px-4 py-2 font-mono text-xs text-zinc-200">{c.name}</td>
                    <td className="px-4 py-2 font-mono text-xs text-zinc-400">{c.image}</td>
                    <td className="px-4 py-2 text-xs text-zinc-500">{c.uptime}</td>
                    <td className="px-4 py-2">
                      <Dot healthy={true} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </WorkspaceSection>

      {/* Control plane cards */}
      <WorkspaceSection
        title="Control Plane — Service Health"
        description="HTTP/TCP health checks against the control node. Langfuse, PostgreSQL, SPIRE, MinIO."
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {health?.control_plane.map((svc) => (
            <div
              key={svc.name}
              className={`rounded-lg border p-3 ${
                svc.healthy
                  ? "border-zinc-800 bg-zinc-900/50"
                  : "border-red-900/60 bg-red-950/30"
              }`}
            >
              <p className="text-xs font-medium text-zinc-300">{svc.name}</p>
              <p className="mt-0.5 font-mono text-xs text-zinc-500">:{svc.port}</p>
              <div className="mt-2">
                <Dot healthy={svc.healthy} />
              </div>
            </div>
          ))}
          {!health && (
            <div className="col-span-full py-6 text-center text-sm text-zinc-500">
              Checking control-plane services…
            </div>
          )}
        </div>
      </WorkspaceSection>

      {/* Inference nodes */}
      <WorkspaceSection title="Inference Nodes — Ollama Status">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-4">
          <NodeStatus />
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
