"use client";

import { ModelSelector } from "@/components/chat/model-selector";
import { GitHubConnect } from "@/components/settings/github-connect";
import { useToolsStore } from "@/lib/stores/tools-store";
import { useMonitorStore } from "@/lib/stores/monitor-store";
import { DASHBOARDS } from "@/components/monitor/dashboard-selector";
import { useAccess } from "@/lib/hooks/use-access";
import { Settings } from "lucide-react";

const TOOL_OPTIONS = [
  { id: "openhands", label: "OpenHands" },
  { id: "ide-devops", label: "IDE (DevOps)" },
  { id: "ide-coding", label: "IDE (Coding)" },
  { id: "open-webui", label: "Open WebUI" },
];

export default function SettingsPage() {
  const { activeTab, setActiveTab } = useToolsStore();
  const { activeDashboard, setActiveDashboard } = useMonitorStore();
  const { isAdmin, loading: accessLoading, securityLevel } = useAccess();

  const modelAccessMessage = accessLoading
    ? "Checking access level..."
    : isAdmin
      ? "Admin access verified. Claude models are available for this session."
      : `Access level: ${securityLevel || "anonymous"}. Claude models are hidden and non-admin sessions use local-model fallback.`;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 border-b border-[var(--chat-border)] bg-[var(--chat-surface)] px-4 py-3">
        <Settings size={18} className="text-[var(--chat-muted)]" />
        <h1 className="text-sm font-medium text-[var(--chat-text)]">Settings</h1>
      </div>
      <div className="flex-1 overflow-y-auto p-6 max-w-2xl">
        <div className="space-y-8">
          {/* Chat */}
          <section>
            <h2 className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wider mb-4">Chat</h2>
            <div>
              <label className="text-sm text-[var(--chat-text)] mb-2 block">Default Model</label>
              <ModelSelector />
              <p className="mt-2 text-xs text-[var(--chat-muted)]">
                {modelAccessMessage}
              </p>
            </div>
          </section>

          {/* Connected Accounts */}
          <section>
            <h2 className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wider mb-4">Connected Accounts</h2>
            <GitHubConnect />
            <p className="mt-2 text-xs text-[var(--chat-muted)]">
              Connect your GitHub account to access GitHub Models (GPT-4o, Claude, Llama, and more) directly in the chat and editor.
            </p>
          </section>

          {/* Tools */}
          <section>
            <h2 className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wider mb-4">Tools</h2>
            <div>
              <label className="text-sm text-[var(--chat-text)] mb-2 block">Default Tool Tab</label>
              <select
                value={activeTab}
                onChange={(e) => setActiveTab(e.target.value)}
                className="w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg px-3 py-2 text-sm text-[var(--chat-text)] focus:outline-none focus:border-[var(--chat-accent)]"
              >
                {TOOL_OPTIONS.map((t) => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
            </div>
          </section>

          {/* Monitor */}
          <section>
            <h2 className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wider mb-4">Monitor</h2>
            <div>
              <label className="text-sm text-[var(--chat-text)] mb-2 block">Default Dashboard</label>
              <select
                value={activeDashboard}
                onChange={(e) => setActiveDashboard(e.target.value)}
                className="w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg px-3 py-2 text-sm text-[var(--chat-text)] focus:outline-none focus:border-[var(--chat-accent)]"
              >
                {DASHBOARDS.map((d) => (
                  <option key={d.uid} value={d.uid}>{d.label}</option>
                ))}
              </select>
            </div>
          </section>

          {/* About */}
          <section>
            <h2 className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wider mb-4">About</h2>
            <div className="space-y-2 text-sm text-[var(--chat-muted)]">
              <p>Hive Mind Workspace v1.0</p>
              <p>Backend: {process.env.NEXT_PUBLIC_API_BASE_URL || "Agent Runtime"}</p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
