"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Plus, Trash2, MoreHorizontal, GitBranch, FileCode, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useDevProjectStore, type DevProject } from "@/lib/stores/dev-project-store";
import { useDevEditorStore } from "@/lib/stores/dev-editor-store";

// ---------------------------------------------------------------------------
// Types matching the backend API response
// ---------------------------------------------------------------------------
interface ApiProject {
  id: string;
  name: string;
  source: "blank" | "git_url";
  git_url?: string;
  git_ref?: string;
  local_path?: string;
}

// ---------------------------------------------------------------------------
// Helper: map backend shape → store shape
// ---------------------------------------------------------------------------
function toStoreProject(p: ApiProject): DevProject {
  return {
    id: p.id,
    name: p.name,
    repoUrl: p.git_url,
    localPath: p.local_path,
  };
}

// ---------------------------------------------------------------------------
// Source badge
// ---------------------------------------------------------------------------
function SourceBadge({ source }: { source: "blank" | "git_url" }) {
  if (source === "git_url") {
    return (
      <span
        className="inline-flex items-center gap-0.5 px-1 py-px rounded text-[10px] font-medium"
        style={{
          background: "color-mix(in srgb, var(--chat-accent) 15%, transparent)",
          color: "var(--chat-accent)",
          border: "1px solid color-mix(in srgb, var(--chat-accent) 30%, transparent)",
        }}
      >
        <GitBranch size={9} />
        git
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-0.5 px-1 py-px rounded text-[10px] font-medium"
      style={{
        background: "color-mix(in srgb, var(--chat-muted) 15%, transparent)",
        color: "var(--chat-subtle, var(--chat-muted))",
        border: "1px solid color-mix(in srgb, var(--chat-muted) 25%, transparent)",
      }}
    >
      <FileCode size={9} />
      blank
    </span>
  );
}

// ---------------------------------------------------------------------------
// Inline creation form
// ---------------------------------------------------------------------------
interface CreateFormProps {
  onCancel: () => void;
  onCreated: (project: ApiProject) => void;
}

function CreateForm({ onCancel, onCreated }: CreateFormProps) {
  const [name, setName] = useState("");
  const [source, setSource] = useState<"blank" | "git_url">("blank");
  const [gitUrl, setGitUrl] = useState("");
  const [gitRef, setGitRef] = useState("main");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const body: Record<string, string> = {
        name: name.trim(),
        source,
      };
      if (source === "git_url") {
        if (!gitUrl.trim()) {
          setError("Git URL is required.");
          setSubmitting(false);
          return;
        }
        body.git_url = gitUrl.trim();
        body.git_ref = gitRef.trim() || "main";
      }
      const res = await fetch("/api/backend/v1/dev/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        setError(`Failed to create project (${res.status})${text ? `: ${text}` : ""}`);
        return;
      }
      const created: ApiProject = await res.json();
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="p-3 flex flex-col gap-2.5">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[11px] font-semibold text-[var(--chat-text)] uppercase tracking-wide">
          New project
        </span>
        <button
          type="button"
          onClick={onCancel}
          className="text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
          aria-label="Cancel"
        >
          <X size={13} />
        </button>
      </div>

      {/* Name */}
      <div className="flex flex-col gap-1">
        <label className="text-[11px] text-[var(--chat-muted)]">Name</label>
        <input
          ref={nameRef}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="my-project"
          required
          className={cn(
            "w-full px-2.5 py-1.5 text-[12px] rounded-md outline-none transition-colors",
            "bg-[var(--chat-panel)] border border-[var(--chat-border)]",
            "text-[var(--chat-text)] placeholder-[var(--chat-muted)]",
            "focus:border-[var(--chat-accent)]"
          )}
        />
      </div>

      {/* Source radio */}
      <div className="flex flex-col gap-1">
        <span className="text-[11px] text-[var(--chat-muted)]">Source</span>
        <div className="flex items-center gap-3">
          {(["blank", "git_url"] as const).map((s) => (
            <label
              key={s}
              className="flex items-center gap-1.5 cursor-pointer text-[12px] text-[var(--chat-text)]"
            >
              <input
                type="radio"
                name="source"
                value={s}
                checked={source === s}
                onChange={() => setSource(s)}
                className="accent-[var(--chat-accent)]"
              />
              {s === "blank" ? "Blank" : "From Git URL"}
            </label>
          ))}
        </div>
      </div>

      {/* Git fields */}
      {source === "git_url" && (
        <>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-[var(--chat-muted)]">Git URL</label>
            <input
              type="text"
              value={gitUrl}
              onChange={(e) => setGitUrl(e.target.value)}
              placeholder="https://github.com/user/repo.git"
              className={cn(
                "w-full px-2.5 py-1.5 text-[12px] rounded-md outline-none transition-colors",
                "bg-[var(--chat-panel)] border border-[var(--chat-border)]",
                "text-[var(--chat-text)] placeholder-[var(--chat-muted)]",
                "focus:border-[var(--chat-accent)]"
              )}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-[var(--chat-muted)]">Ref</label>
            <input
              type="text"
              value={gitRef}
              onChange={(e) => setGitRef(e.target.value)}
              placeholder="main"
              className={cn(
                "w-full px-2.5 py-1.5 text-[12px] rounded-md outline-none transition-colors",
                "bg-[var(--chat-panel)] border border-[var(--chat-border)]",
                "text-[var(--chat-text)] placeholder-[var(--chat-muted)]",
                "focus:border-[var(--chat-accent)]"
              )}
            />
          </div>
        </>
      )}

      {error && (
        <p className="text-[11px] text-red-400">{error}</p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-0.5">
        <button
          type="submit"
          disabled={submitting || !name.trim()}
          className={cn(
            "flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors",
            "bg-[var(--chat-accent)] text-white hover:opacity-90",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          {submitting && <Loader2 size={11} className="animate-spin" />}
          Create
        </button>
        <button
          type="button"
          onClick={onCancel}
          className={cn(
            "flex-1 px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors",
            "bg-[var(--chat-panel)] border border-[var(--chat-border)]",
            "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          )}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Delete confirmation dialog
// ---------------------------------------------------------------------------
interface DeleteConfirmProps {
  project: ApiProject;
  onConfirm: () => void;
  onCancel: () => void;
  deleting: boolean;
  error?: string | null;
}

function DeleteConfirm({ project, onConfirm, onCancel, deleting, error }: DeleteConfirmProps) {
  return (
    <div className="p-3 flex flex-col gap-2.5">
      <p className="text-[12px] text-[var(--chat-text)]">
        Delete project <strong>{project.name}</strong>? This will remove all files.
      </p>
      {error && (
        <p className="text-[11px] text-red-400">{error}</p>
      )}
      <div className="flex items-center gap-2">
        <button
          onClick={onConfirm}
          disabled={deleting}
          className={cn(
            "flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors",
            "bg-red-600 text-white hover:bg-red-500",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          {deleting && <Loader2 size={11} className="animate-spin" />}
          Delete
        </button>
        <button
          onClick={onCancel}
          disabled={deleting}
          className={cn(
            "flex-1 px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors",
            "bg-[var(--chat-panel)] border border-[var(--chat-border)]",
            "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          )}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Project row
// ---------------------------------------------------------------------------
interface ProjectRowProps {
  project: ApiProject;
  isActive: boolean;
  onSelect: () => void;
  onDeleteRequest: () => void;
}

function ProjectRow({ project, isActive, onSelect, onDeleteRequest }: ProjectRowProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="relative group flex items-center">
      <button
        onClick={onSelect}
        className={cn(
          "flex-1 flex items-center gap-2 px-2.5 py-2 text-left rounded-sm transition-colors min-w-0",
          isActive
            ? "bg-[var(--chat-accent-soft)] text-[var(--chat-text)]"
            : "text-[var(--chat-text)] hover:bg-[var(--hover-tint)]"
        )}
      >
        <span className="flex-1 min-w-0 text-[12px] truncate">{project.name}</span>
        <SourceBadge source={project.source} />
        {isActive && (
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--chat-accent)] flex-shrink-0" />
        )}
      </button>

      {/* "..." menu trigger — visible on row hover or when open */}
      <div className={cn("absolute right-0 flex-shrink-0 pr-1", menuOpen ? "flex" : "hidden group-hover:flex")}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen((v) => !v);
          }}
          className={cn(
            "w-6 h-6 flex items-center justify-center rounded transition-colors",
            "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)]"
          )}
          aria-label="Project options"
        >
          <MoreHorizontal size={12} />
        </button>
      </div>

      {/* Context menu */}
      {menuOpen && (
        <>
          <div className="fixed inset-0 z-[60]" onClick={() => setMenuOpen(false)} />
          <div
            className="absolute right-1 top-full mt-0.5 w-36 rounded-md overflow-hidden z-[70]"
            style={{
              background: "var(--chat-elevated)",
              border: "1px solid var(--chat-border)",
              boxShadow: "var(--elev-3)",
            }}
          >
            <button
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen(false);
                onDeleteRequest();
              }}
              className="w-full flex items-center gap-2 px-2.5 py-2 text-[12px] text-red-400 hover:bg-[var(--hover-tint)] transition-colors"
            >
              <Trash2 size={12} />
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main ProjectSwitcher
// ---------------------------------------------------------------------------
export function ProjectSwitcher() {
  const { currentProjectId, projects, setCurrentProjectId, setProjects, addProject, removeProject } =
    useDevProjectStore();
  const { hasUnsavedChanges } = useDevEditorStore();

  const [open, setOpen] = useState(false);
  const [apiProjects, setApiProjects] = useState<ApiProject[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ApiProject | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentProject = apiProjects.find((p) => p.id === currentProjectId);

  // Fetch projects from backend
  const fetchProjects = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/backend/v1/dev/projects");
      if (!res.ok) return;
      const data = await res.json();
      const list: ApiProject[] = data.projects ?? [];
      setApiProjects(list);
      setProjects(list.map(toStoreProject));
    } catch {
      // silently ignore
    } finally {
      setLoading(false);
    }
  };

  // Load on mount
  useEffect(() => {
    fetchProjects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setShowCreate(false);
        setDeleteTarget(null);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  function handleOpen() {
    setOpen((v) => {
      const next = !v;
      if (next) {
        setShowCreate(false);
        setDeleteTarget(null);
        fetchProjects();
      }
      return next;
    });
  }

  function handleSelect(project: ApiProject) {
    if (
      project.id !== currentProjectId &&
      hasUnsavedChanges &&
      !window.confirm("You have unsaved changes in the editor. Switch project and discard them?")
    ) {
      return;
    }
    setCurrentProjectId(project.id);
    setOpen(false);
    setShowCreate(false);
    setDeleteTarget(null);
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const res = await fetch(`/api/backend/v1/dev/projects/${deleteTarget.id}`, {
        method: "DELETE",
      });
      if (res.ok || res.status === 204) {
        removeProject(deleteTarget.id);
        setApiProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id));
        setDeleteTarget(null);
      } else {
        const text = await res.text().catch(() => "");
        setDeleteError(`Delete failed (${res.status})${text ? `: ${text}` : ""}`);
      }
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Network error");
    } finally {
      setDeleting(false);
    }
  }

  function handleCreated(created: ApiProject) {
    addProject(toStoreProject(created));
    setApiProjects((prev) => [...prev, created]);
    setCurrentProjectId(created.id);
    setShowCreate(false);
    setOpen(false);
  }

  return (
    <div ref={containerRef} className="relative flex-shrink-0">
      {/* Trigger button */}
      <button
        onClick={handleOpen}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] font-medium rounded-md transition-colors border",
          open
            ? "bg-[var(--chat-elevated)] text-[var(--chat-text)] border-[var(--chat-accent)]"
            : "bg-[var(--chat-panel)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] border-[var(--chat-border)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_50%,var(--chat-text))]"
        )}
        title="Switch project"
      >
        <span className={cn(open ? "text-[var(--chat-accent)]" : "")}>
          {currentProject
            ? <span className="w-2 h-2 rounded-full bg-[var(--chat-accent)] inline-block" />
            : <span className="w-2 h-2 rounded-full bg-[var(--chat-border)] inline-block" />
          }
        </span>
        <span className="max-w-[120px] truncate">
          {currentProject ? currentProject.name : "No project"}
        </span>
        <ChevronDown
          size={11}
          className={cn(
            "text-[var(--chat-subtle,var(--chat-muted))] transition-transform flex-shrink-0",
            open && "rotate-180"
          )}
        />
      </button>

      {/* Dropdown popover */}
      {open && (
        <div
          className="absolute left-0 top-full mt-1.5 w-64 rounded-md overflow-hidden z-50"
          style={{
            background: "var(--chat-elevated)",
            border: "1px solid var(--chat-border)",
            boxShadow: "var(--elev-3)",
          }}
        >
          {deleteTarget ? (
            <DeleteConfirm
              project={deleteTarget}
              onConfirm={handleDeleteConfirm}
              onCancel={() => { setDeleteTarget(null); setDeleteError(null); }}
              deleting={deleting}
              error={deleteError}
            />
          ) : showCreate ? (
            <CreateForm
              onCancel={() => setShowCreate(false)}
              onCreated={handleCreated}
            />
          ) : (
            <>
              {/* Project list */}
              <div className="max-h-56 overflow-y-auto p-1">
                {loading ? (
                  <div className="flex items-center justify-center py-4 gap-2 text-[var(--chat-muted)]">
                    <Loader2 size={13} className="animate-spin" />
                    <span className="text-[12px]">Loading…</span>
                  </div>
                ) : apiProjects.length === 0 ? (
                  <div className="py-4 text-center text-[12px] text-[var(--chat-muted)]">
                    No projects yet
                  </div>
                ) : (
                  apiProjects.map((project) => (
                    <ProjectRow
                      key={project.id}
                      project={project}
                      isActive={project.id === currentProjectId}
                      onSelect={() => handleSelect(project)}
                      onDeleteRequest={() => setDeleteTarget(project)}
                    />
                  ))
                )}
              </div>

              {/* Separator + New project */}
              <div style={{ borderTop: "1px solid var(--chat-border)" }} className="p-1">
                <button
                  onClick={() => setShowCreate(true)}
                  className="w-full flex items-center gap-2 px-2.5 py-2 text-[12px] text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--hover-tint)] rounded-sm transition-colors"
                >
                  <Plus size={13} className="text-[var(--chat-accent)]" />
                  New project
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
