"use client";

import { useSettingsStore } from "@/lib/stores/settings-store";
import { ModelSelector } from "@/components/chat/model-selector";
import { Settings } from "lucide-react";

export default function SettingsPage() {
  const mode = useSettingsStore((s) => s.mode);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 border-b border-zinc-800 bg-[#0e1117] px-4 py-3">
        <Settings size={18} className="text-zinc-400" />
        <h1 className="text-sm font-medium text-zinc-300">Settings</h1>
      </div>
      <div className="flex-1 overflow-y-auto p-6 max-w-2xl">
        <div className="space-y-6">
          <div>
            <h2 className="text-sm font-medium text-zinc-300 mb-2">Default Model</h2>
            <ModelSelector />
          </div>
          <div>
            <h2 className="text-sm font-medium text-zinc-300 mb-2">Interface Mode</h2>
            <p className="text-xs text-zinc-500">
              Current mode: <span className="text-cyan-400">{mode}</span>
            </p>
            <p className="text-xs text-zinc-600 mt-1">
              Switch modes using the toggle in the sidebar.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
