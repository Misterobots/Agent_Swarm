"use client";

import { RefreshCw, ShieldCheck } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { useEffect, useMemo, useState } from "react";
import { fetchOpsHealth } from "@/lib/api/ops";
import { fetchGovernanceRequests } from "@/lib/api/workspaces";
import type { OpsHealth } from "@/types/ops";
import type { GovernanceRequest } from "@/types/workspaces";

export default function ControlRoomPage() {
  const [health, setHealth] = useState<OpsHealth | null>(null);
  const [requests, setRequests] = useState<GovernanceRequest[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [h, r] = await Promise.all([fetchOpsHealth(), fetchGovernanceRequests()]);
    setHealth(h);
    setRequests(r);
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
      title="Control Room"
      description="Protected operations surface for runtime testing and maintenance actions."
      icon={ShieldCheck}
    >
      <WorkspaceSection title="Operational Snapshot">
        <div className="mb-4 flex items-center justify-end">
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
            <p className="text-xs text-[var(--chat-muted)]">System Status</p>
            <p className="mt-1 text-sm font-medium text-[var(--chat-text)]">{health?.status ?? "Unknown"}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
            <p className="text-xs text-[var(--chat-muted)]">Running Containers</p>
            <p className="mt-1 text-sm font-medium text-[var(--chat-text)]">{health?.running_count ?? 0}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
            <p className="text-xs text-[var(--chat-muted)]">Unhealthy Services</p>
            <p className="mt-1 text-sm font-medium text-red-400">{unhealthy.length}</p>
          </div>
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
            <p className="text-xs text-[var(--chat-muted)]">Pending Approvals</p>
            <p className="mt-1 text-sm font-medium text-amber-400">{pending.length}</p>
          </div>
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Maintenance Queue">
        <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
          {pending.length === 0 ? (
            <p className="text-sm text-[var(--chat-muted)]">No pending governance requests.</p>
          ) : (
            <ul className="space-y-2">
              {pending.slice(0, 8).map((req) => (
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

      <WorkspaceSection title="Reliability Actions">
        <div className="grid gap-3 md:grid-cols-3">
          {[
            {
              title: "Swarm Reliability Test",
              body: "Run test_endpoints.sh and test_host.sh from the execution plane.",
              cmd: "bash test_endpoints.sh && bash test_host.sh",
            },
            {
              title: "Logs Diagnostic",
              body: "Collect docker compose logs and inspect recent backend errors.",
              cmd: "docker compose logs --tail=200",
            },
            {
              title: "Node Health Check",
              body: "Validate all inference nodes and loaded model state.",
              cmd: "GET /api/v1/health/nodes",
            },
          ].map((card) => (
            <div key={card.title} className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
              <p className="text-sm font-medium text-[var(--chat-text)]">{card.title}</p>
              <p className="mt-1 text-xs text-[var(--chat-muted)]">{card.body}</p>
              <code className="mt-2 block rounded bg-[var(--chat-bg)] px-2 py-1 text-xs text-[var(--chat-muted)]">
                {card.cmd}
              </code>
            </div>
          ))}
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}