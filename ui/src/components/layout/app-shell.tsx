"use client";

import { useState } from "react";
import { Sidebar } from "./sidebar";
import { cn } from "@/lib/utils/cn";
import { PanelLeftClose, PanelLeft } from "lucide-react";
import { useSettingsStore } from "@/lib/stores/settings-store";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const theme = useSettingsStore((s) => s.theme);

  return (
    <div data-theme={theme} className="flex h-screen bg-[var(--chat-bg,#0e1117)] text-[var(--chat-text,#e4e4e7)]">
      {/* Sidebar */}
      <div
        className={cn(
          "transition-all duration-200 flex-shrink-0 overflow-hidden",
          sidebarOpen ? "w-64" : "w-0"
        )}
      >
        <div className="w-64 h-full">
          <Sidebar />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toggle button */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute top-3 left-2 z-10 p-1.5 rounded-md text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-panel)] transition-colors"
          style={{ left: sidebarOpen ? "17rem" : "0.5rem" }}
        >
          {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
        </button>

        {children}
      </div>
    </div>
  );
}
