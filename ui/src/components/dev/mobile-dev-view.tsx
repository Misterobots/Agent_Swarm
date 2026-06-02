"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useDevProjectStore } from "@/lib/stores/dev-project-store";
import { useDevEditorStore } from "@/lib/stores/dev-editor-store";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GitStatus {
  branch: string;
  ahead: number;
  behind: number;
}

interface Goal {
  id: string;
  objective: string;
  status: string;
}

// ---------------------------------------------------------------------------
// Card wrapper
// ---------------------------------------------------------------------------

function SectionCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg p-3">
      {children}
    </div>
  );
}

function SectionHeader({ label }: { label: string }) {
  return (
    <p className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wide mb-2">
      {label}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MobileDevView() {
  const router = useRouter();
  const { currentProjectId, projects } = useDevProjectStore();
  const { activeFile } = useDevEditorStore();

  const [gitStatus, setGitStatus] = useState<GitStatus | null>(null);
  const [gitError, setGitError] = useState(false);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [goalsLoading, setGoalsLoading] = useState(true);

  const project = projects.find((p) => p.id === currentProjectId) ?? null;

  // Fetch git status
  useEffect(() => {
    let cancelled = false;
    fetch("/api/devops/git/status?node=workspace")
      .then(async (res) => {
        if (!res.ok) throw new Error("non-ok");
        const data = await res.json();
        if (!cancelled) {
          setGitStatus({
            branch: data.branch ?? "unknown",
            ahead: data.ahead ?? 0,
            behind: data.behind ?? 0,
          });
        }
      })
      .catch(() => {
        if (!cancelled) setGitError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch goals
  useEffect(() => {
    let cancelled = false;
    fetch("/api/backend/v1/goals?limit=5")
      .then(async (res) => {
        if (!res.ok) throw new Error("non-ok");
        const data = await res.json();
        if (!cancelled) {
          const list: Goal[] = Array.isArray(data)
            ? data
            : Array.isArray(data?.goals)
            ? data.goals
            : [];
          setGoals(list.slice(0, 5));
        }
      })
      .catch(() => {
        if (!cancelled) setGoals([]);
      })
      .finally(() => {
        if (!cancelled) setGoalsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Status badge color mapping
  function statusColor(status: string): string {
    switch (status?.toLowerCase()) {
      case "done":
      case "complete":
      case "completed":
        return "text-[var(--chat-accent)] bg-[var(--chat-accent-soft)]";
      case "in_progress":
      case "active":
        return "text-[color:color-mix(in_srgb,var(--chat-accent)_60%,var(--chat-text))] bg-[var(--chat-elevated)]";
      default:
        return "text-[var(--chat-muted)] bg-[var(--chat-surface)]";
    }
  }

  return (
    <div className="h-full overflow-y-auto p-4 flex flex-col gap-4">

      {/* Section 1 — Current project */}
      <SectionCard>
        <SectionHeader label="Current Project" />
        {project ? (
          <div className="flex items-center gap-2">
            <span className="text-[var(--chat-accent)] text-sm">◆</span>
            <span className="text-sm font-medium text-[var(--chat-text)] truncate">
              {project.name}
            </span>
          </div>
        ) : (
          <p className="text-sm text-[var(--chat-muted)]">No project open</p>
        )}
      </SectionCard>

      {/* Section 2 — Active file */}
      <SectionCard>
        <SectionHeader label="Active File" />
        {activeFile ? (
          <p className="text-xs font-mono text-[var(--chat-text)] truncate leading-relaxed">
            {activeFile}
          </p>
        ) : (
          <p className="text-sm text-[var(--chat-muted)]">No file open</p>
        )}
      </SectionCard>

      {/* Section 3 — Git status */}
      <SectionCard>
        <SectionHeader label="Git Status" />
        {gitError || (!gitStatus && !gitError) ? (
          <p className="text-sm font-mono text-[var(--chat-muted)]">
            {gitError ? "--" : "Loading…"}
          </p>
        ) : gitStatus ? (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-mono text-[var(--chat-text)]">
              {gitStatus.branch}
            </span>
            {(gitStatus.ahead > 0 || gitStatus.behind > 0) && (
              <span className="text-xs font-mono text-[var(--chat-muted)]">
                {gitStatus.ahead > 0 && `↑${gitStatus.ahead}`}
                {gitStatus.ahead > 0 && gitStatus.behind > 0 && " "}
                {gitStatus.behind > 0 && `↓${gitStatus.behind}`}
              </span>
            )}
          </div>
        ) : null}
      </SectionCard>

      {/* Section 4 — Goals */}
      <SectionCard>
        <SectionHeader label="Goals" />
        {goalsLoading ? (
          <p className="text-sm text-[var(--chat-muted)]">Loading…</p>
        ) : goals.length === 0 ? (
          <p className="text-sm text-[var(--chat-muted)]">No goals</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {goals.map((goal) => (
              <li key={goal.id} className="flex items-start gap-2">
                <span className="text-xs text-[var(--chat-text)] flex-1 leading-relaxed">
                  {goal.objective}
                </span>
                {goal.status && (
                  <span
                    className={`shrink-0 text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${statusColor(goal.status)}`}
                  >
                    {goal.status.replace(/_/g, " ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* Section 5 — Footer */}
      <SectionCard>
        <div className="flex flex-col items-center gap-3 text-center">
          <button
            onClick={() => router.push("/chat")}
            className="px-4 py-2 text-sm font-medium rounded-md bg-[var(--chat-elevated)] border border-[var(--chat-border)] text-[var(--chat-text)] hover:text-[var(--chat-accent)] transition-colors"
          >
            Open Chat →
          </button>
          <p className="text-xs text-[var(--chat-muted)]">
            Open Memex on desktop to use the editor and terminal.
          </p>
        </div>
      </SectionCard>

    </div>
  );
}
