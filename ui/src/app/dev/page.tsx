"use client";

import { DevWorkspace } from "@/components/dev/dev-workspace";
import { useDevStore } from "@/lib/stores/dev-store";
import { FolderTree, Eye, Settings, Bot, Layers } from "lucide-react";

export default function DevPage() {
  const {
    showFileTree,
    agentEnabled,
    setShowFileTree,
    setAgentEnabled,
  } = useDevStore();

  return (
    <div className="h-screen flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-[var(--chat-bg)] border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-2">
          <h1 className="text-sm font-semibold text-[var(--chat-text)]">Developer Workspace</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* Panel toggles */}
          <button
            onClick={() => setShowFileTree(!showFileTree)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors ${
              showFileTree
                ? "bg-[var(--chat-accent)] text-white"
                : "bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
            }`}
            title="Toggle file tree"
          >
            <FolderTree size={14} />
            Files
          </button>

          {/* Agent mode toggle */}
          <button
            onClick={() => setAgentEnabled(!agentEnabled)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors ${
              agentEnabled
                ? "bg-green-600 text-white"
                : "bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
            }`}
            title="Toggle agent mode (file + terminal access)"
          >
            <Bot size={14} />
            Agent Mode
          </button>

          <button
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
            title="Workspace settings"
          >
            <Settings size={14} />
          </button>
        </div>
      </div>

      {/* Workspace */}
      <div className="flex-1">
        <DevWorkspace />
      </div>
    </div>
  );
}
