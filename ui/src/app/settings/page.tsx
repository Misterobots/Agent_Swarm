"use client";

import { ModelSelector } from "@/components/chat/model-selector";
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
      <div className="flex items-center gap-2 border-b border-zinc-800 bg-[#0e1117] px-4 py-3">
        <Settings size={18} className="text-zinc-400" />
        <h1 className="text-sm font-medium text-zinc-300">Settings</h1>
      </div>
      <div className="flex-1 overflow-y-auto p-6 max-w-2xl">
        <div className="space-y-8">
          {/* Chat */}
          <section>
            <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Chat</h2>
            <div>
              <label className="text-sm text-zinc-300 mb-2 block">Default Model</label>
              <ModelSelector />
              <p className="mt-2 text-xs text-zinc-500">
                {modelAccessMessage}
              </p>
            </div>
          </section>

          {/* Tools */}
          <section>
            <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Tools</h2>
            <div>
              <label className="text-sm text-zinc-300 mb-2 block">Default Tool Tab</label>
              <select
                value={activeTab}
                onChange={(e) => setActiveTab(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-cyan-800"
              >
                {TOOL_OPTIONS.map((t) => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
            </div>
          </section>

          {/* Monitor */}
          <section>
            <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Monitor</h2>
            <div>
              <label className="text-sm text-zinc-300 mb-2 block">Default Dashboard</label>
              <select
                value={activeDashboard}
                onChange={(e) => setActiveDashboard(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-cyan-800"
              >
                {DASHBOARDS.map((d) => (
                  <option key={d.uid} value={d.uid}>{d.label}</option>
                ))}
              </select>
            </div>
          </section>

          {/* About */}
          <section>
            <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">About</h2>
            <div className="space-y-2 text-sm text-zinc-500">
              <p>Hive Mind Workspace v1.0</p>
              <p>Backend: {process.env.NEXT_PUBLIC_API_BASE_URL || "Agent Runtime"}</p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
