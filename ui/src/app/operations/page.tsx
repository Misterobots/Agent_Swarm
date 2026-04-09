"use client";

import Link from "next/link";
import { RefreshCw, Shield, TerminalSquare } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { OpsDashboard } from "@/components/ops/ops-dashboard";
import { useEffect, useMemo, useState } from "react";
import { fetchOpsHealth } from "@/lib/api/ops";
import { fetchGovernanceRequests } from "@/lib/api/workspaces";
import type { OpsHealth } from "@/types/ops";
import type { GovernanceRequest } from "@/types/workspaces";

export default function OperationsPage() {
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
      title="Operations"
      description="Infrastructure dashboard, administrative controls, and runtime operations."
      icon={Shield}
    >
      {/* ── Ops Dashboard Section ──────────────────────────────────── */}
      <WorkspaceSection title="Infrastructure Overview">
        <OpsDashboard />
      </WorkspaceSection>

      {/* ── Admin Surface ──────────────────────────────────────────── */}
      <WorkspaceSection title="Admin Surface">
        <div className="mb-4 flex justify-end">
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Pending Approvals</p>
            <p className="mt-1 text-xl font-semibold text-amber-400">{pending.length}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Unhealthy Services</p>
            <p className="mt-1 text-xl font-semibold text-red-400">{unhealthy.length}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
            <p className="text-xs text-[var(--chat-muted)]">Cluster Containers</p>
            <p className="mt-1 text-xl font-semibold text-[var(--chat-text)]">{health?.running_count ?? 0}</p>
          </div>
        </div>
      </WorkspaceSection>

      {/* ── Node Container Summary ─────────────────────────────────── */}
      <WorkspaceSection title="Node Container Summary" description="Quick view of container counts by cluster node.">
        <div className="grid gap-3 md:grid-cols-3">
          {(health?.nodes ?? []).map((node) => (
            <div key={node.name} className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4">
              <p className="text-sm font-medium text-[var(--chat-text)]">{node.name}</p>
              <p className="mt-0.5 font-mono text-xs text-[var(--chat-muted)]">{node.ip}</p>
              <p className="mt-2 text-2xl font-semibold text-[var(--chat-text)]">{node.running_count}</p>
              <p className="text-xs text-[var(--chat-muted)]">running containers</p>
            </div>
          ))}
        </div>
      </WorkspaceSection>

      {/* ── Control-Plane Services ─────────────────────────────────── */}
      <WorkspaceSection title="Control-Plane Services">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {health?.control_plane.map((svc) => (
            <div key={svc.name} className={`rounded-lg border p-3 ${svc.healthy ? "border-[var(--chat-border)] bg-[var(--chat-panel)]" : "border-red-900/60 bg-red-950/30"}`}>
              <p className="text-xs font-medium text-[var(--chat-text)]">{svc.name}</p>
              <p className="mt-0.5 font-mono text-xs text-[var(--chat-muted)]">:{svc.port}</p>
              <p className={`mt-2 text-xs ${svc.healthy ? "text-emerald-400" : "text-red-400"}`}>{svc.healthy ? "Healthy" : "Down"}</p>
            </div>
          ))}
        </div>
      </WorkspaceSection>

      {/* ── Pending Governance Queue ───────────────────────────────── */}
      <WorkspaceSection title="Pending Governance Queue">
        <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
          {pending.length === 0 ? (
            <p className="text-sm text-[var(--chat-muted)]">No pending requests.</p>
          ) : (
            <ul className="space-y-2">
              {pending.slice(0, 6).map((req) => (
                <li key={req.id} className="rounded border border-[var(--chat-border)] bg-[var(--chat-surface)] p-2.5">
                  <p className="text-xs text-[var(--chat-text)]">
                    <span className="font-mono text-[var(--chat-muted)]">{req.id}</span> · {req.type} · {req.status}
                  </p>
                  <p className="mt-1 text-xs text-[var(--chat-muted)]">{req.description}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </WorkspaceSection>

      {/* ── Action Runbooks ────────────────────────────────────────── */}
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
            <div key={card.title} className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
              <p className="text-sm font-medium text-[var(--chat-text)]">{card.title}</p>
              <p className="mt-1 text-xs text-[var(--chat-muted)]">{card.body}</p>
              <code className="mt-2 block rounded bg-[var(--chat-bg)] px-2 py-1 text-xs text-[var(--chat-muted)]">{card.cmd}</code>
            </div>
          ))}
        </div>
      </WorkspaceSection>

      {/* ── Quick Links ────────────────────────────────────────────── */}
      <WorkspaceSection title="Quick Links">
        <div className="mt-1 grid gap-3 md:grid-cols-4">
          <Link href="/monitoring/control-room" className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3 hover:border-[var(--chat-accent)]">
            <p className="text-sm font-medium text-[var(--chat-text)]">Control Room</p>
            <p className="mt-1 text-xs text-[var(--chat-muted)]">Operations and maintenance queue</p>
          </Link>
          <Link href="/governance" className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3 hover:border-[var(--chat-accent)]">
            <p className="text-sm font-medium text-[var(--chat-text)]">Governance Queue</p>
            <p className="mt-1 text-xs text-[var(--chat-muted)]">Approve and create governance requests</p>
          </Link>
          <Link href="/monitoring/dashboard" className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3 hover:border-[var(--chat-accent)]">
            <p className="text-sm font-medium text-[var(--chat-text)]">Health Dashboard</p>
            <p className="mt-1 text-xs text-[var(--chat-muted)]">Cluster-wide container visibility</p>
          </Link>
          <Link href="/monitoring/evidence-locker" className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3 hover:border-[var(--chat-accent)]">
            <p className="text-sm font-medium text-[var(--chat-text)]">Evidence Locker</p>
            <p className="mt-1 text-xs text-[var(--chat-muted)]">Runbook and architecture evidence docs</p>
          </Link>
        </div>
      </WorkspaceSection>

      <div className="hidden"><TerminalSquare /></div>
    </WorkspaceShell>
  );
}
