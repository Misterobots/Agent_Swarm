"use client";

import { useState } from "react";
import { useDevStore } from "@/lib/stores/dev-store";
import { FileIcon, FolderIcon, GitBranch, ChevronRight, ChevronDown } from "lucide-react";

interface FileNode {
  name: string;
  path: string;
  type: "file" | "directory";
  children?: FileNode[];
}

export function FileTree() {
  const { selectedNode, activeFile, setActiveFile, setSelectedNode, gitBranch } = useDevStore();
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["/workspace"]));
  const [files, setFiles] = useState<FileNode[]>([
    {
      name: "workspace",
      path: "/workspace",
      type: "directory",
      children: [
        { name: "README.md", path: "/workspace/README.md", type: "file" },
        { name: "src", path: "/workspace/src", type: "directory", children: [] },
      ],
    },
  ]);

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

  const handleFileClick = (node: FileNode) => {
    if (node.type === "file") {
      setActiveFile(node.path);
      // TODO: Load file content into editor
    } else {
      toggleExpand(node.path);
    }
  };

  const renderNode = (node: FileNode, depth: number = 0) => {
    const isExpanded = expanded.has(node.path);
    const isActive = node.type === "file" && node.path === activeFile;

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
              <FolderIcon size={14} />
            </>
          ) : (
            <FileIcon size={14} />
          )}
          <span className="text-xs">{node.name}</span>
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

      {/* File Tree */}
      <div className="flex-1 overflow-y-auto">
        {files.map((node) => renderNode(node))}
      </div>
    </div>
  );
}
