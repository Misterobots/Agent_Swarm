"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Editor from "@monaco-editor/react";
import { FileText } from "lucide-react";
import { useDevProjectStore } from "@/lib/stores/dev-project-store";
import { registerPanel } from "./dev-panels-registry";

// ── File API helpers ───────────────────────────────────────────────────────

const NOTES_PATH = ".memex/notes.md";
const AUTOSAVE_DELAY = 2000;

interface FileContentResponse {
  content: string;
  encoding: "utf8" | "base64";
  mime: string;
  size: number;
}

async function fetchNotes(projectId: string): Promise<string | null> {
  const url = `/api/backend/v1/dev/files/content?project_id=${encodeURIComponent(projectId)}&path=${encodeURIComponent(NOTES_PATH)}`;
  const res = await fetch(url);
  if (res.status === 404) return "";
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data: FileContentResponse = await res.json();
  return data.content;
}

async function saveNotes(projectId: string, content: string): Promise<void> {
  const res = await fetch("/api/backend/v1/dev/files/content", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      path: NOTES_PATH,
      content,
      encoding: "utf8",
    }),
  });
  if (!res.ok && res.status !== 204) {
    throw new Error(`HTTP ${res.status}`);
  }
}

// ── Format timestamp ───────────────────────────────────────────────────────

function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

// ── Main panel component ───────────────────────────────────────────────────

export function NotesPanel() {
  const currentProjectId = useDevProjectStore((s) => s.currentProjectId);

  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [saving, setSaving] = useState(false);

  // Track the projectId that was last loaded so we don't double-load
  const loadedProjectId = useRef<string | null>(null);
  // Debounce timer ref
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Save in-flight ref (to avoid races)
  const savingRef = useRef(false);

  // ── Load notes when project changes ───────────────────────────────────

  useEffect(() => {
    // Cancel any pending autosave from the previous project
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
      debounceTimer.current = null;
    }

    if (!currentProjectId) {
      setContent("");
      setError(null);
      setLoading(false);
      setSavedAt(null);
      loadedProjectId.current = null;
      return;
    }

    if (loadedProjectId.current === currentProjectId) return;

    let cancelled = false;

    setLoading(true);
    setError(null);
    setSavedAt(null);

    fetchNotes(currentProjectId)
      .then((text) => {
        if (cancelled) return;
        setContent(text ?? "");
        loadedProjectId.current = currentProjectId;
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load notes");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [currentProjectId]);

  // ── Debounced autosave ─────────────────────────────────────────────────

  const triggerSave = useCallback(
    (newContent: string, projectId: string) => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
      debounceTimer.current = setTimeout(async () => {
        if (savingRef.current) return;
        savingRef.current = true;
        setSaving(true);
        try {
          await saveNotes(projectId, newContent);
          setSavedAt(new Date());
        } catch (err) {
          setError(err instanceof Error ? err.message : "Save failed");
        } finally {
          savingRef.current = false;
          setSaving(false);
        }
      }, AUTOSAVE_DELAY);
    },
    []
  );

  const handleChange = useCallback(
    (value: string | undefined) => {
      const newContent = value ?? "";
      setContent(newContent);
      if (currentProjectId) {
        triggerSave(newContent, currentProjectId);
      }
    },
    [currentProjectId, triggerSave]
  );

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, []);

  // ── Render ─────────────────────────────────────────────────────────────

  if (!currentProjectId) {
    return (
      <div className="flex flex-col h-full bg-[var(--chat-bg)] overflow-hidden">
        <NotesPanelHeader savedAt={null} saving={false} />
        <div className="flex-1 flex flex-col items-center justify-center px-6 py-10 text-center">
          <FileText
            size={28}
            className="text-[var(--chat-muted)] opacity-40 mb-3"
          />
          <p className="text-[12px] text-[var(--chat-muted)] leading-relaxed">
            Open a project to view its notes
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)] overflow-hidden">
      <NotesPanelHeader savedAt={savedAt} saving={saving} />

      {error && (
        <div className="px-3 py-1.5 bg-[color:color-mix(in_srgb,#ef4444_12%,transparent)] border-b border-[color:color-mix(in_srgb,#ef4444_25%,var(--chat-border))]">
          <p className="text-[11px] text-red-400">{error}</p>
        </div>
      )}

      <div className="flex-1 min-h-0 relative">
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-[12px] text-[var(--chat-muted)] animate-pulse">
              Loading notes…
            </p>
          </div>
        ) : (
          <Editor
            height="100%"
            language="markdown"
            value={content}
            onChange={handleChange}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: "off",
              scrollBeyondLastLine: false,
              wordWrap: "on",
              tabSize: 2,
              automaticLayout: true,
              padding: { top: 8, bottom: 8 },
              renderLineHighlight: "none",
              cursorBlinking: "smooth",
              smoothScrolling: true,
              folding: false,
              renderWhitespace: "none",
              overviewRulerLanes: 0,
              hideCursorInOverviewRuler: true,
            }}
          />
        )}
      </div>
    </div>
  );
}

// ── Panel header sub-component ─────────────────────────────────────────────

function NotesPanelHeader({
  savedAt,
  saving,
}: {
  savedAt: Date | null;
  saving: boolean;
}) {
  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--chat-border)] shrink-0">
      <div className="flex items-center gap-2">
        <FileText size={14} className="text-[var(--chat-accent)]" />
        <div>
          <span className="text-[12px] font-semibold text-[var(--chat-text)]">
            Project Notes
          </span>
          <span className="ml-2 text-[10px] text-[var(--chat-muted)]">
            .memex/notes.md
          </span>
        </div>
      </div>
      <div className="text-[10px] text-[var(--chat-muted)] shrink-0">
        {saving ? (
          <span className="opacity-60">Saving…</span>
        ) : savedAt ? (
          <span>Saved {formatTime(savedAt)}</span>
        ) : null}
      </div>
    </div>
  );
}

// ── Self-registration ──────────────────────────────────────────────────────

registerPanel({
  id: "notes",
  title: "Notes",
  position: "right",
  icon: React.createElement(FileText, { size: 14 }),
  component: NotesPanel,
  toolbarOrder: 40,
  className: "w-[420px]",
});
