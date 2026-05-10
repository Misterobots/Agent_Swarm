"use client";

import { useCallback, useEffect, useState } from "react";
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
  const themeMode = useSettingsStore((s) => s.themeMode);

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

  // Apply theme + mode to <html>. Mode is resolved (system -> dark|light)
  // and re-resolves live if the user changes their OS preference.
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);

    // Legacy debug-flag: localStorage["memex-show-legacy"] === "1" enables
    // the retired 8-theme bundle. Off by default.
    const legacy = typeof window !== "undefined" && window.localStorage.getItem("memex-show-legacy") === "1";
    if (legacy) root.setAttribute("data-legacy-themes", "1");
    else root.removeAttribute("data-legacy-themes");

    if (theme !== "memex") {
      // Legacy themes don't use data-mode
      root.removeAttribute("data-mode");
      return;
    }

    const apply = (resolved: "dark" | "light") => root.setAttribute("data-mode", resolved);

    if (themeMode === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      apply(mq.matches ? "dark" : "light");
      const onChange = (e: MediaQueryListEvent) => apply(e.matches ? "dark" : "light");
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
    apply(themeMode);
  }, [theme, themeMode]);

  // Stable callbacks — must not recreate on every render or MobileDrawer's
  // useEffect([pathname, onClose]) will fire and immediately close the drawer.
  const handleOpenDrawer = useCallback(() => setDrawerOpen(true), []);
  const handleCloseDrawer = useCallback(() => setDrawerOpen(false), []);

  return (
    <div data-theme={theme} className="flex h-dvh bg-[var(--chat-bg,#0e1117)] text-[var(--chat-text,#e4e4e7)]">
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
      <div className={cn("flex-1 flex flex-col min-w-0 overflow-hidden", isMobile && "pb-14")}>
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
        <BottomTabBar onMenuPress={handleOpenDrawer} />
      )}

      {/* Mobile Drawer */}
      {isMobile && (
        <MobileDrawer open={drawerOpen} onClose={handleCloseDrawer} />
      )}
    </div>
  );
}
