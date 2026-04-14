"use client";

import { Archive, Copy, RefreshCw } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { useEffect, useMemo, useState } from "react";
import {
  fetchEvidenceContent,
  fetchEvidenceFiles,
  fetchEvidenceFolders,
} from "@/lib/api/workspaces";
import type { EvidenceFile } from "@/types/workspaces";

export default function EvidenceLockerPage() {
  const [folders, setFolders] = useState<string[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>("");
  const [files, setFiles] = useState<EvidenceFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const folderCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const folder of folders) {
      counts[folder] = folder === selectedFolder ? files.length : 0;
    }
    return counts;
  }, [folders, files, selectedFolder]);

  async function refreshFolders() {
    setLoading(true);
    try {
      const nextFolders = await fetchEvidenceFolders();
      setFolders(nextFolders);
      if (!selectedFolder && nextFolders.length > 0) {
        setSelectedFolder(nextFolders[0]);
      }
    } catch (err) {
      console.error("[EvidenceLocker] Failed to load folders:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshFolders();
  }, []);

  useEffect(() => {
    if (!selectedFolder) return;
    fetchEvidenceFiles(selectedFolder).then((data) => {
      setFiles(data);
      setSelectedFile(data[0]?.name ?? "");
    });
  }, [selectedFolder]);

  useEffect(() => {
    if (!selectedFolder || !selectedFile) {
      setContent("");
      return;
    }
    fetchEvidenceContent(selectedFolder, selectedFile).then((data) => {
      setContent(data?.content ?? "");
    });
  }, [selectedFolder, selectedFile]);

  async function copyContent() {
    if (!content) return;
    await navigator.clipboard.writeText(content);
  }

  return (
    <WorkspaceShell
      title="Evidence Locker"
      description="Operational documents, evidence bundles, specs, and compliance artifacts."
      icon={Archive}
    >
      <WorkspaceSection title="Document Browser">
        <div className="mb-4 flex items-center justify-between">
          <div className="text-xs text-[var(--chat-muted)]">
            Source: <span className="font-mono">/workspace/docs</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={copyContent}
              disabled={!content}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] disabled:opacity-50"
            >
              <Copy size={12} /> Copy
            </button>
            <button
              onClick={refreshFolders}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] disabled:opacity-50"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
        </div>

        <div className="mb-3 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] px-3 py-2 text-xs text-[var(--chat-muted)]">
          {selectedFolder ? `${selectedFolder} / ${selectedFile || "(no file selected)"}` : "Select a folder"}
        </div>

        <div className="grid gap-4 md:grid-cols-[240px_280px_1fr]">
          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
            <p className="mb-2 text-xs font-medium text-[var(--chat-muted)]">Folders</p>
            <div className="space-y-1">
              {folders.map((folder) => (
                <button
                  key={folder}
                  onClick={() => setSelectedFolder(folder)}
                  className={`w-full rounded px-2 py-1.5 text-left text-sm ${
                    selectedFolder === folder
                      ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent)]"
                      : "text-[var(--chat-muted)] hover:bg-[var(--chat-surface)]"
                  }`}
                >
                  <span>{folder}</span>
                  <span className="ml-2 text-[10px] text-[var(--chat-muted)]">({folderCounts[folder] ?? 0})</span>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-panel)] p-3">
            <p className="mb-2 text-xs font-medium text-[var(--chat-muted)]">Files</p>
            <div className="space-y-1">
              {files.length === 0 && (
                <p className="px-2 py-2 text-xs text-[var(--chat-muted)]">No files in folder.</p>
              )}
              {files.map((file) => (
                <button
                  key={file.name}
                  onClick={() => setSelectedFile(file.name)}
                  className={`w-full rounded px-2 py-1.5 text-left ${
                    selectedFile === file.name
                      ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent)]"
                      : "text-[var(--chat-muted)] hover:bg-[var(--chat-surface)]"
                  }`}
                >
                  <p className="truncate text-sm">{file.name}</p>
                  <p className="text-xs text-[var(--chat-muted)]">{(file.size / 1024).toFixed(1)} KB</p>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-[var(--chat-border)] bg-[var(--chat-bg)] p-3">
            <p className="mb-2 text-xs font-medium text-[var(--chat-muted)]">{selectedFile || "File content"}</p>
            <pre className="max-h-[64vh] overflow-auto whitespace-pre-wrap rounded bg-[var(--chat-surface)] p-3 font-mono text-xs text-[var(--chat-text)]">
              {content || "Select a file to view its contents."}
            </pre>
          </div>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
