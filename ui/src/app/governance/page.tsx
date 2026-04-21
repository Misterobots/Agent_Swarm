"use client";

import { Gavel, RefreshCw } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { useMemo, useState, useEffect } from "react";
import {
  createGovernanceRequest,
  fetchGovernanceRequests,
  updateGovernanceStatus,
} from "@/lib/api/workspaces";
import type { GovernanceRequest } from "@/types/workspaces";

function relativeTime(iso: string) {
  const ms = Date.now() - Date.parse(iso);
  const min = Math.floor(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

export default function GovernancePage() {
  const [requests, setRequests] = useState<GovernanceRequest[]>([]);
  const [statusFilter, setStatusFilter] = useState<"ALL" | GovernanceRequest["status"]>("ALL");
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [newType, setNewType] = useState<GovernanceRequest["type"]>("FEATURE");
  const [newDescription, setNewDescription] = useState("");
  const [newUser, setNewUser] = useState("coding_user");
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    const rows = await fetchGovernanceRequests();
    rows.sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
    setRequests(rows);
    setLoading(false);
  }

  async function submitRequest() {
    if (!newDescription.trim()) return;
    setSubmitting(true);
    const created = await createGovernanceRequest({
      type: newType,
      description: newDescription.trim(),
      user: newUser.trim() || "coding_user",
    });
    if (created) {
      setRequests((prev) => [created, ...prev]);
      setNewDescription("");
    }
    setSubmitting(false);
  }

  async function setStatus(reqId: string, status: GovernanceRequest["status"]) {
    const updated = await updateGovernanceStatus(reqId, status, `Updated in Next UI to ${status}`);
    if (!updated) return;
    setRequests((prev) => prev.map((r) => (r.id === reqId ? updated : r)));
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    if (statusFilter === "ALL") return requests;
    return requests.filter((r) => r.status === statusFilter);
  }, [requests, statusFilter]);

  const statusCounts = useMemo(() => {
    const base = { ALL: requests.length, PENDING: 0, ASSESSING: 0, APPROVED: 0, REJECTED: 0, COMPLETED: 0, FAILED: 0 };
    for (const row of requests) {
      base[row.status] += 1;
    }
    return base;
  }, [requests]);

  return (
    <WorkspaceShell
      title="Governance"
      description="Approval queues, review workflows, and decision audit surfaces."
      icon={Gavel}
    >
      <WorkspaceSection title="Create Governance Request" description="Uses X-Swarm-Source key from UI environment.">
        <div className="grid gap-3 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-4 md:grid-cols-[180px_1fr_180px_auto]">
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as GovernanceRequest["type"])}
            className="rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
          >
            {(["PACKAGE", "MODEL", "PERMISSION", "FEATURE", "GROUNDING_WEB", "GROUNDING_DOCS", "GROUNDING_FILE", "OTHER"] as const).map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
          <input
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            placeholder="Describe the request (install package, model promotion, permission, etc.)"
            className="rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
          />
          <input
            value={newUser}
            onChange={(e) => setNewUser(e.target.value)}
            placeholder="User"
            className="rounded border border-[var(--chat-border)] bg-[var(--chat-bg)] px-3 py-2 text-sm text-[var(--chat-text)]"
          />
          <button
            onClick={submitRequest}
            disabled={submitting || !newDescription.trim()}
            className="rounded border border-[var(--chat-accent)] bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] px-3 py-2 text-sm text-[var(--chat-accent)] disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Submit"}
          </button>
        </div>
      </WorkspaceSection>

      <WorkspaceSection title="Approval Workflow">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {(["ALL", "PENDING", "ASSESSING", "APPROVED", "REJECTED", "COMPLETED", "FAILED"] as const).map(
            (status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`rounded-full border px-3 py-1 text-xs ${
                  statusFilter === status
                    ? "border-[var(--chat-accent)] bg-[color:color-mix(in_srgb,var(--chat-accent)_16%,transparent)] text-[var(--chat-accent)]"
                    : "border-[var(--chat-border)] bg-[var(--chat-panel)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
                }`}
              >
                {status} ({statusCounts[status]})
              </button>
            )
          )}
          <button
            onClick={load}
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        <div className="overflow-x-auto rounded-lg border border-[var(--chat-border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--chat-border)] bg-[var(--chat-surface)]">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">ID</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">Type</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">Description</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">User</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">Status</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">When</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--chat-muted)]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-[var(--chat-muted)]">Loading governance queue...</td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-[var(--chat-muted)]">No governance requests found.</td>
                </tr>
              ) : (
                filtered.flatMap((req) => {
                  const rows = [
                    <tr
                      key={req.id}
                      className="border-b border-[var(--chat-border)] align-top hover:bg-[var(--chat-surface)] cursor-pointer"
                      onClick={() => setExpandedId((prev) => (prev === req.id ? null : req.id))}
                    >
                      <td className="px-4 py-2.5 font-mono text-xs text-[var(--chat-text)]">{req.id}</td>
                      <td className="px-4 py-2.5 text-xs text-[var(--chat-muted)]">{req.type}</td>
                      <td className="px-4 py-2.5 text-xs text-[var(--chat-text)] max-w-[320px] truncate">{req.description}</td>
                      <td className="px-4 py-2.5 text-xs text-[var(--chat-muted)]">{req.user}</td>
                      <td className="px-4 py-2.5 text-xs text-[var(--chat-text)]">{req.status}</td>
                      <td className="px-4 py-2.5 text-xs text-[var(--chat-muted)]">{relativeTime(req.timestamp)}</td>
                      <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <div className="flex flex-wrap gap-1">
                          <button onClick={() => setStatus(req.id, "APPROVED")} className="rounded border border-emerald-800/80 bg-emerald-950/30 px-2 py-1 text-xs text-emerald-400">Approve</button>
                          <button onClick={() => setStatus(req.id, "REJECTED")} className="rounded border border-red-900/80 bg-red-950/30 px-2 py-1 text-xs text-red-400">Reject</button>
                          <button onClick={() => setStatus(req.id, "COMPLETED")} className="rounded border border-[var(--chat-accent)]/40 bg-[var(--chat-accent)]/10 px-2 py-1 text-xs text-[var(--chat-accent)]">Complete</button>
                        </div>
                      </td>
                    </tr>,
                  ];

                  if (expandedId === req.id) {
                    rows.push(
                      <tr key={`${req.id}-expanded`} className="border-b border-[var(--chat-border)] bg-[var(--chat-surface)]">
                        <td colSpan={7} className="px-4 py-3">
                          <p className="text-xs text-[var(--chat-text)]">{req.description}</p>
                          <p className="mt-2 text-[11px] text-[var(--chat-muted)]">{new Date(req.timestamp).toLocaleString()}</p>
                          {req.assessment_notes?.length > 0 ? (
                            <div className="mt-3 space-y-1">
                              {req.assessment_notes.map((note, idx) => (
                                <p key={`${req.id}-note-${idx}`} className="rounded bg-[var(--chat-panel)] px-2 py-1 text-xs text-[var(--chat-muted)]">{note}</p>
                              ))}
                            </div>
                          ) : (
                            <p className="mt-2 text-xs text-[var(--chat-muted)]">No assessment notes yet.</p>
                          )}
                        </td>
                      </tr>
                    );
                  }

                  return rows;
                })
              )}
            </tbody>
          </table>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
