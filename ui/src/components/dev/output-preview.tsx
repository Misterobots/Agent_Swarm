"use client";

import { useState } from "react";
import { useDevStore } from "@/lib/stores/dev-store";
import { Globe, FileText, Network } from "lucide-react";

type PreviewTab = "preview" | "logs" | "network";

export function OutputPreview() {
  const { previewUrl } = useDevStore();
  const [activeTab, setActiveTab] = useState<PreviewTab>("preview");
  const [logs, setLogs] = useState<string[]>([
    "[12:34:56] Server started on port 3000",
    "[12:35:01] Connected to database",
  ]);

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)] border-t border-[var(--chat-border)]">
      {/* Tab Bar */}
      <div className="flex items-center border-b border-[var(--chat-border)] bg-[var(--chat-bg)]">
        <button
          onClick={() => setActiveTab("preview")}
          className={`flex items-center gap-2 px-3 py-2 text-xs transition-colors ${
            activeTab === "preview"
              ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)]"
              : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          }`}
        >
          <Globe size={14} />
          Preview
        </button>
        <button
          onClick={() => setActiveTab("logs")}
          className={`flex items-center gap-2 px-3 py-2 text-xs transition-colors ${
            activeTab === "logs"
              ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)]"
              : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          }`}
        >
          <FileText size={14} />
          Logs
        </button>
        <button
          onClick={() => setActiveTab("network")}
          className={`flex items-center gap-2 px-3 py-2 text-xs transition-colors ${
            activeTab === "network"
              ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)]"
              : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          }`}
        >
          <Network size={14} />
          Network
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "preview" && (
          <iframe
            src={previewUrl}
            className="w-full h-full border-0"
            sandbox="allow-same-origin allow-scripts allow-forms"
            title="App Preview"
          />
        )}
        
        {activeTab === "logs" && (
          <div className="h-full overflow-y-auto p-2 font-mono text-xs text-[var(--chat-text)] bg-[#0a0a14]">
            {logs.map((log, i) => (
              <div key={i} className="py-0.5">
                {log}
              </div>
            ))}
          </div>
        )}
        
        {activeTab === "network" && (
          <div className="h-full overflow-y-auto p-4 text-xs text-[var(--chat-muted)]">
            <p>Network inspector coming soon...</p>
          </div>
        )}
      </div>
    </div>
  );
}
