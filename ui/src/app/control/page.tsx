"use client";

import Link from "next/link";
import { RefreshCw, Shield, TerminalSquare } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { useEffect, useMemo, useState } from "react";
import { fetchOpsHealth } from "@/lib/api/ops";
import { fetchGovernanceRequests } from "@/lib/api/workspaces";
import type { OpsHealth } from "@/types/ops";
import type { GovernanceRequest } from "@/types/workspaces";

export default function ControlPage() {
  const [health, setHealth] = useState<OpsHealth | null>(null);
  const [requests, setRequests] = useState<GovernanceRequest[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [healthData, reqs] = await Promise.all([fetchOpsHealth(), fetchGovernanceRequests()]);
    setHealth(healthData);
    setRequests(reqs);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  const pending = useMemo(
    () => requests.filter((r) => r.status === "PENDING" || r.status === "ASSESSING"),
    [requests]
  );
  const unhealthy = health?.control_plane.filter((s) => !s.healthy) ?? [];

  return (
    <WorkspaceShell
      title="Control"
      description="Administrative control surface for runtime operations and managed actions."
      icon={Shield}
    >
      <WorkspaceSection title="Admin Surface">
        <div className="mb-4 flex justify-end">
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-400 hover:text-zinc-200"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs text-zinc-500">Pending Approvals</p>
            <p className="mt-1 text-xl font-semibold text-amber-400">{pending.length}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs text-zinc-500">Unhealthy Services</p>
            <p className="mt-1 text-xl font-semibold text-red-400">{unhealthy.length}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs text-zinc-500">Cluster Containers</p>
            <p className="mt-1 text-xl font-semibold text-zinc-200">{health?.running_count ?? 0}</p>
          </div>
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Node Container Summary" description="Quick view of container counts by cluster node.">
        <div className="grid gap-3 md:grid-cols-3">
          {(health?.nodes ?? []).map((node) => (
            <div key={node.name} className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-sm font-medium text-zinc-200">{node.name}</p>
              <p className="mt-0.5 font-mono text-xs text-zinc-500">{node.ip}</p>
              <p className="mt-2 text-2xl font-semibold text-zinc-100">{node.running_count}</p>
              <p className="text-xs text-zinc-500">running containers</p>
            </div>
          ))}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Control-Plane Services">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {health?.control_plane.map((svc) => (
            <div key={svc.name} className={`rounded-lg border p-3 ${svc.healthy ? "border-zinc-800 bg-zinc-900/50" : "border-red-900/60 bg-red-950/30"}`}>
              <p className="text-xs font-medium text-zinc-300">{svc.name}</p>
              <p className="mt-0.5 font-mono text-xs text-zinc-500">:{svc.port}</p>
              <p className={`mt-2 text-xs ${svc.healthy ? "text-emerald-400" : "text-red-400"}`}>{svc.healthy ? "Healthy" : "Down"}</p>
            </div>
          ))}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Pending Governance Queue">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
          {pending.length === 0 ? (
            <p className="text-sm text-zinc-500">No pending requests.</p>
          ) : (
            <ul className="space-y-2">
              {pending.slice(0, 6).map((req) => (
                <li key={req.id} className="rounded border border-zinc-800 bg-zinc-950/40 p-2.5">
                  <p className="text-xs text-zinc-300">
                    <span className="font-mono text-zinc-500">{req.id}</span> · {req.type} · {req.status}
                  </p>
                  <p className="mt-1 text-xs text-zinc-400">{req.description}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Action Runbooks" description="Display-first command references. Inline execution can be added next.">
        <div className="grid gap-3 md:grid-cols-3">
          {[
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
          ].map((card) => (
            <div key={card.title} className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
              <p className="text-sm font-medium text-zinc-200">{card.title}</p>
              <p className="mt-1 text-xs text-zinc-500">{card.body}</p>
              <code className="mt-2 block rounded bg-zinc-950 px-2 py-1 text-xs text-zinc-400">{card.cmd}</code>
            </div>
          ))}
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Quick Links">
        <div className="mt-1 grid gap-3 md:grid-cols-4">
          <Link href="/monitoring/control-room" className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 hover:border-[var(--chat-accent)]">
            <p className="text-sm font-medium text-zinc-200">Control Room</p>
            <p className="mt-1 text-xs text-zinc-500">Operations and maintenance queue</p>
          </Link>
          <Link href="/governance" className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 hover:border-[var(--chat-accent)]">
            <p className="text-sm font-medium text-zinc-200">Governance Queue</p>
            <p className="mt-1 text-xs text-zinc-500">Approve and create governance requests</p>
          </Link>
          <Link href="/monitoring/dashboard" className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 hover:border-[var(--chat-accent)]">
            <p className="text-sm font-medium text-zinc-200">Health Dashboard</p>
            <p className="mt-1 text-xs text-zinc-500">Cluster-wide container visibility</p>
          </Link>
          <Link href="/monitoring/evidence-locker" className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 hover:border-[var(--chat-accent)]">
            <p className="text-sm font-medium text-zinc-200">Evidence Locker</p>
            <p className="mt-1 text-xs text-zinc-500">Runbook and architecture evidence docs</p>
          </Link>
        </div>
      </WorkspaceSection>

      <div className="hidden"><TerminalSquare /></div>
    </WorkspaceShell>
  );
}
