"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "./sidebar";
import { BottomTabBar } from "./bottom-tab-bar";
import { MobileDrawer } from "./mobile-drawer";
import { cn } from "@/lib/utils/cn";
import { PanelLeftClose, PanelLeft } from "lucide-react";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useIsMobile } from "@/lib/hooks/use-mobile";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { isMobile, isTablet } = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const theme = useSettingsStore((s) => s.theme);

  // Close sidebar on mobile/tablet by default
  useEffect(() => {
    if (isMobile) {
      setSidebarOpen(false);
    } else if (isTablet) {
      setSidebarOpen(false);
    } else {
      setSidebarOpen(true);
    }
  }, [isMobile, isTablet]);

  // Sync data-theme to <html> so body/root-level styles are also theme-aware
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  return (
    <div data-theme={theme} className="flex h-dvh overflow-x-hidden bg-[var(--chat-bg,#0e1117)] text-[var(--chat-text,#e4e4e7)]">
      {/* Desktop/Tablet Sidebar */}
      {!isMobile && (
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
      )}

      {/* Main content */}
      <div className={cn("flex-1 flex flex-col min-w-0", isMobile && "pb-14")}>
        {/* Toggle button — desktop/tablet only */}
        {!isMobile && (
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="absolute top-3 left-2 z-10 p-1.5 rounded-md text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-panel)] transition-colors"
            style={{ left: sidebarOpen ? "17rem" : "0.5rem" }}
          >
            {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
          </button>
        )}

        {children}
      </div>

      {/* Mobile Bottom Tab Bar */}
      {isMobile && (
        <BottomTabBar onMenuPress={() => setDrawerOpen(true)} />
      )}

      {/* Mobile Drawer */}
      {isMobile && (
        <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      )}
    </div>
  );
}
