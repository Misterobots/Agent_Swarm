"use client";

import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "./sidebar";
import { BottomTabBar } from "./bottom-tab-bar";
import { MobileDrawer } from "./mobile-drawer";
import { cn } from "@/lib/utils/cn";
import { PanelLeft } from "lucide-react";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useIsMobile } from "@/lib/hooks/use-mobile";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { isMobile, isTablet } = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const theme = useSettingsStore((s) => s.theme);
  const themeMode = useSettingsStore((s) => s.themeMode);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const persistedSidebarOpen = useSettingsStore((s) => s.sidebarOpen);
  const setPersistedSidebarOpen = useSettingsStore((s) => s.setSidebarOpen);

  // Effective sidebar state: persisted preference on desktop, forced closed on
  // mobile/tablet (those use the drawer). Toggling on desktop writes through
  // to the store so the choice survives reloads.
  const sidebarOpen = isMobile || isTablet ? false : persistedSidebarOpen;
  const setSidebarOpen = (open: boolean) => {
    if (isMobile || isTablet) return; // desktop-only preference
    setPersistedSidebarOpen(open);
  };

  // Apply theme + mode to <html>. Mode is resolved (system -> dark|light)
  // and re-resolves live if the user changes their OS preference.
  useEffect(() => {
    const root = document.documentElement;

    // Legacy debug-flag: localStorage["memex-show-legacy"] === "1" enables
    // the retired theme bundle (ember/slate/hacker/cyberpunk/etc.).
    const legacy = typeof window !== "undefined" && window.localStorage.getItem("memex-show-legacy") === "1";
    if (legacy) root.setAttribute("data-legacy-themes", "1");
    else root.removeAttribute("data-legacy-themes");

    // Self-heal: if a stale persisted theme survived the v1->v2 migration
    // and the legacy flag isn't on, coerce back to "memex" so the mode
    // toggle (light/dark/system) actually attaches.
    if (theme !== "memex" && !legacy) {
      setTheme("memex");
      return;
    }

    root.setAttribute("data-theme", theme);

    if (theme !== "memex") {
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
  }, [theme, themeMode, setTheme]);

  // Stable callbacks — must not recreate on every render or MobileDrawer's
  // useEffect([pathname, onClose]) will fire and immediately close the drawer.
  const handleOpenDrawer = useCallback(() => setDrawerOpen(true), []);
  const handleCloseDrawer = useCallback(() => setDrawerOpen(false), []);

  return (
    <div className="app-shell-root flex h-dvh bg-[var(--chat-bg,#0e1117)] text-[var(--chat-text,#e4e4e7)]">
      {/* Desktop/Tablet Sidebar */}
      {!isMobile && (
        <div
          className={cn(
            "transition-all duration-200 flex-shrink-0 overflow-hidden",
            sidebarOpen ? "w-64" : "w-0"
          )}
        >
          <div className="w-64 h-full">
            <Sidebar onCollapse={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}

      {/* Main content */}
      <div
        className={cn("relative flex-1 flex flex-col min-w-0 overflow-hidden", isMobile && "pb-14")}
        style={{
          // Page headers reserve this much left-padding so the floating
          // expand handle (when sidebar is collapsed) doesn't collide.
          ["--sidebar-rail-pad" as string]: !isMobile && !sidebarOpen ? "2.75rem" : "0px",
        }}
      >
        {/* Edge-anchored expand handle — only shows when sidebar is collapsed */}
        {!isMobile && !sidebarOpen && (
          <button
            onClick={() => setSidebarOpen(true)}
            className="absolute top-3 left-3 z-20 inline-flex items-center justify-center w-8 h-8 rounded-md bg-[var(--chat-panel)] text-[var(--chat-muted)] border border-[var(--chat-border)] hover:text-[var(--chat-text)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_50%,var(--chat-text))] transition-colors"
            style={{ boxShadow: "var(--elev-1), var(--inset-highlight)" }}
            title="Expand sidebar"
            aria-label="Expand sidebar"
          >
            <PanelLeft size={15} />
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
