"use client";

import { Archive, Copy, FileText, Folder, RefreshCw } from "lucide-react";
import { WorkspaceSection, WorkspaceShell } from "@/components/workspace/workspace-shell";
import { Button, Card } from "@/components/ui";
import { useEffect, useMemo, useState } from "react";
import {
  fetchEvidenceContent,
  fetchEvidenceFiles,
  fetchEvidenceFolders,
} from "@/lib/api/workspaces";
import type { EvidenceFile } from "@/types/workspaces";
import { cn } from "@/lib/utils/cn";

export default function EvidenceLockerPage() {
  const [folders, setFolders] = useState<string[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>("");
  const [files, setFiles] = useState<EvidenceFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

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
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <WorkspaceShell
      title="Evidence Locker"
      description="Operational documents, evidence bundles, specs, and compliance artifacts."
      icon={Archive}
      actions={
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={copyContent}
            disabled={!content}
            iconLeft={<Copy size={13} />}
          >
            {copied ? "Copied" : "Copy"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={refreshFolders}
            iconLeft={<RefreshCw size={13} className={loading ? "animate-spin" : ""} />}
          >
            Refresh
          </Button>
        </div>
      }
    >
      <WorkspaceSection title="Document Browser">
        {/* Breadcrumb */}
        <div
          className="mb-4 flex items-center gap-2 rounded-md px-3 py-2 text-[12px]"
          style={{
            background: "var(--chat-panel)",
            border: "1px solid var(--chat-border)",
          }}
        >
          <span className="text-[var(--chat-subtle)] font-mono">/workspace/docs</span>
          {selectedFolder && (
            <>
              <span className="text-[var(--chat-subtle)]">/</span>
              <span className="text-[var(--chat-text)] font-mono">{selectedFolder}</span>
            </>
          )}
          {selectedFile && (
            <>
              <span className="text-[var(--chat-subtle)]">/</span>
              <span className="text-[var(--chat-accent)] font-mono">{selectedFile}</span>
            </>
          )}
        </div>

        <div className="grid gap-4 md:grid-cols-[220px_260px_1fr]">
          {/* Folders */}
          <Card padding="sm">
            <p className="px-2 mb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
              Folders
            </p>
            <div className="space-y-px">
              {folders.length === 0 && !loading && (
                <p className="px-2 py-2 text-[12px] text-[var(--chat-muted)]">No folders.</p>
              )}
              {folders.map((folder) => {
                const isActive = selectedFolder === folder;
                return (
                  <button
                    key={folder}
                    onClick={() => setSelectedFolder(folder)}
                    className={cn(
                      "w-full flex items-center gap-2 rounded-sm px-2 py-1.5 text-left text-[13px] transition-colors",
                      isActive
                        ? "bg-[var(--chat-accent-soft)] text-[var(--chat-accent-strong)]"
                        : "text-[var(--chat-muted)] hover:bg-[var(--hover-tint)] hover:text-[var(--chat-text)]"
                    )}
                  >
                    <Folder size={13} className={cn("flex-shrink-0", isActive && "text-[var(--chat-accent)]")} />
                    <span className="flex-1 truncate">{folder}</span>
                    <span className="text-[10px] tabular-nums text-[var(--chat-subtle)]">
                      {folderCounts[folder] ?? 0}
                    </span>
                  </button>
                );
              })}
            </div>
          </Card>

          {/* Files */}
          <Card padding="sm">
            <p className="px-2 mb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
              Files
            </p>
            <div className="space-y-px">
              {files.length === 0 ? (
                <p className="px-2 py-2 text-[12px] text-[var(--chat-muted)]">No files in folder.</p>
              ) : (
                files.map((file) => {
                  const isActive = selectedFile === file.name;
                  return (
                    <button
                      key={file.name}
                      onClick={() => setSelectedFile(file.name)}
                      className={cn(
                        "w-full flex items-start gap-2 rounded-sm px-2 py-1.5 text-left transition-colors",
                        isActive
                          ? "bg-[var(--chat-accent-soft)] text-[var(--chat-accent-strong)]"
                          : "text-[var(--chat-muted)] hover:bg-[var(--hover-tint)] hover:text-[var(--chat-text)]"
                      )}
                    >
                      <FileText size={13} className={cn("flex-shrink-0 mt-0.5", isActive && "text-[var(--chat-accent)]")} />
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-[13px]">{file.name}</p>
                        <p className="text-[10px] text-[var(--chat-subtle)] tabular-nums">
                          {(file.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </Card>

          {/* Content */}
          <Card padding="none" className="overflow-hidden">
            <div
              className="px-3 py-2 border-b border-[var(--chat-border)]"
              style={{ background: "color-mix(in srgb, var(--chat-panel) 60%, transparent)" }}
            >
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]">
                {selectedFile || "Document content"}
              </p>
            </div>
            <pre
              className="max-h-[64vh] overflow-auto whitespace-pre-wrap p-4 font-mono text-[12px] text-[var(--chat-text)] leading-relaxed"
              style={{ background: "var(--chat-bg)" }}
            >
              {content || (
                <span className="text-[var(--chat-muted)] italic">
                  Select a file to view its contents.
                </span>
              )}
            </pre>
          </Card>
        </div>
      </WorkspaceSection>
    </WorkspaceShell>
  );
}
