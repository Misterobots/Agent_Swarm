"use client";

import { useState, useEffect } from "react";
import { useDevStore } from "@/lib/stores/dev-store";
import { FileIcon, FolderIcon, GitBranch, ChevronRight, ChevronDown, FolderOpen, Loader2, Search, X } from "lucide-react";

interface FileNode {
  name: string;
  path: string;
  type: "file" | "directory";
  size?: number;
  children?: FileNode[];
}

const LANG_MAP: Record<string, string> = {
  py: "python",
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  json: "json",
  md: "markdown",
  yaml: "yaml",
  yml: "yaml",
  sh: "shell",
  dockerfile: "dockerfile",
  css: "css",
  html: "html",
};

export function FileTree() {
  const {
    selectedNode,
    activeFile,
    setActiveFile,
    setSelectedNode,
    setEditorContent,
    setEditorLanguage,
    gitBranch,
    currentProjectId,
  } = useDevStore();

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [tree, setTree] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingFile, setLoadingFile] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  // Fetch file tree whenever the project changes
  useEffect(() => {
    if (!currentProjectId) {
      setTree([]);
      return;
    }
    setLoading(true);
    fetch(`/api/backend/v1/dev/files/tree?project_id=${currentProjectId}&depth=3`)
      .then((r) => r.json())
      .then((data) => setTree(data.tree ?? []))
      .catch(() => setTree([]))
      .finally(() => setLoading(false));
  }, [currentProjectId]);

  const toggleExpand = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleFileClick = async (node: FileNode) => {
    if (node.type !== "file") {
      toggleExpand(node.path);
      return;
    }
    if (!currentProjectId) return;

    setLoadingFile(node.path);
    try {
      const res = await fetch(
        `/api/backend/v1/dev/files/content?project_id=${currentProjectId}&path=${encodeURIComponent(node.path)}`
      );
      if (!res.ok) return;
      const { content, encoding } = await res.json();
      if (encoding === "base64") return; // skip binary files silently
      setEditorContent(content);
      setActiveFile(node.path);
      const ext = node.name.split(".").pop()?.toLowerCase() ?? "";
      setEditorLanguage(LANG_MAP[ext] ?? "plaintext");
    } finally {
      setLoadingFile(null);
    }
  };

  // Recursive filter — keeps a node if its name matches OR any descendant matches
  const filterTree = (nodes: FileNode[], q: string): FileNode[] => {
    if (!q) return nodes;
    const lower = q.toLowerCase();
    return nodes.reduce<FileNode[]>((acc, node) => {
      if (node.type === "file") {
        if (node.name.toLowerCase().includes(lower)) acc.push(node);
      } else {
        const filteredChildren = filterTree(node.children ?? [], q);
        if (filteredChildren.length > 0 || node.name.toLowerCase().includes(lower)) {
          acc.push({ ...node, children: filteredChildren });
        }
      }
      return acc;
    }, []);
  };

  const visibleTree = filterTree(tree, search);

  const renderNode = (node: FileNode, depth: number = 0): React.ReactNode => {
    const isExpanded = expanded.has(node.path);
    const isActive = node.type === "file" && node.path === activeFile;
    const isLoadingThis = loadingFile === node.path;

    return (
      <div key={node.path}>
        <div
          className={`flex items-center gap-2 px-2 py-1 cursor-pointer hover:bg-[var(--chat-hover)] transition-colors ${
            isActive ? "bg-[var(--chat-accent-dim)] text-[var(--chat-accent)]" : "text-[var(--chat-text)]"
          }`}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          onClick={() => handleFileClick(node)}
        >
          {node.type === "directory" ? (
            <>
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              {isExpanded ? <FolderOpen size={14} className="text-[var(--chat-accent)]" /> : <FolderIcon size={14} className="text-[var(--chat-muted)]" />}
            </>
          ) : (
            <>
              {isLoadingThis ? (
                <Loader2 size={14} className="animate-spin text-[var(--chat-muted)]" />
              ) : (
                <FileIcon size={14} className={isActive ? "text-[var(--chat-accent)]" : "text-[var(--chat-muted)]"} />
              )}
            </>
          )}
          <span className="text-xs truncate">{node.name}</span>
          {node.size !== undefined && node.type === "file" && (
            <span className="ml-auto text-[10px] text-[var(--chat-muted)] shrink-0">
              {node.size < 1024 ? `${node.size}B` : `${(node.size / 1024).toFixed(1)}K`}
            </span>
          )}
        </div>
        {node.type === "directory" && isExpanded && node.children && (
          <div>
            {node.children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)] border-r border-[var(--chat-border)]">
      {/* Node Selector (admin only - TODO: check user role) */}
      <div className="p-2 border-b border-[var(--chat-border)]">
        <select
          value={selectedNode}
          onChange={(e) => setSelectedNode(e.target.value as any)}
          className="w-full px-2 py-1 text-xs bg-[var(--chat-input-bg)] text-[var(--chat-text)] border border-[var(--chat-border)] rounded"
        >
          <option value="workspace">Workspace</option>
          <option value="lovelace">Lovelace</option>
          <option value="turing">Turing</option>
          <option value="hopper">Hopper</option>
        </select>
      </div>

      {/* Git Branch Indicator */}
      {gitBranch[selectedNode] && (
        <div className="flex items-center gap-2 px-2 py-1 text-xs text-[var(--chat-muted)] border-b border-[var(--chat-border)]">
          <GitBranch size={12} />
          <span>{gitBranch[selectedNode]}</span>
        </div>
      )}

      {/* File search */}
      {currentProjectId && (
        <div className="flex items-center gap-1.5 px-2 py-1.5 border-b border-[var(--chat-border)]">
          <Search size={12} className="text-[var(--chat-muted)] shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter files…"
            className="flex-1 bg-transparent text-xs text-[var(--chat-text)] placeholder:text-[var(--chat-muted)] focus:outline-none"
          />
          {search && (
            <button onClick={() => setSearch("")} className="text-[var(--chat-muted)] hover:text-[var(--chat-text)]">
              <X size={12} />
            </button>
          )}
        </div>
      )}

      {/* Active file breadcrumb */}
      {activeFile && !search && (
        <div
          className="flex items-center px-2 py-1 border-b border-[var(--chat-border)] overflow-x-auto"
          style={{ scrollbarWidth: "none" }}
        >
          {activeFile.replace(/^\//, "").split("/").map((seg, i, arr) => (
            <span key={i} className="flex items-center shrink-0">
              {i > 0 && <ChevronRight size={10} className="opacity-30 mx-0.5" />}
              <span
                className={`text-[10px] ${
                  i === arr.length - 1
                    ? "text-[var(--chat-accent)]"
                    : "text-[var(--chat-muted)]"
                }`}
              >
                {seg}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* File Tree */}
      <div className="flex-1 overflow-y-auto">
        {!currentProjectId ? (
          <div className="flex flex-col items-center justify-center h-full px-4 text-center gap-2">
            <FolderIcon size={28} className="text-[var(--chat-muted)] opacity-50" />
            <p className="text-xs text-[var(--chat-muted)]">No project open</p>
            <p className="text-[10px] text-[var(--chat-muted)] opacity-70">Select a project to browse files</p>
          </div>
        ) : loading ? (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <Loader2 size={20} className="animate-spin text-[var(--chat-muted)]" />
            <p className="text-xs text-[var(--chat-muted)]">Loading files…</p>
          </div>
        ) : tree.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full px-4 text-center gap-2">
            <FolderOpen size={28} className="text-[var(--chat-muted)] opacity-50" />
            <p className="text-xs text-[var(--chat-muted)]">Project is empty</p>
          </div>
        ) : visibleTree.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full px-4 text-center gap-2">
            <Search size={24} className="text-[var(--chat-muted)] opacity-40" />
            <p className="text-xs text-[var(--chat-muted)]">No files match &ldquo;{search}&rdquo;</p>
          </div>
        ) : (
          visibleTree.map((node) => renderNode(node))
        )}
      </div>
    </div>
  );
}
