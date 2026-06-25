"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { BottomTabBar } from "./bottom-tab-bar";
import { MobileDrawer } from "./mobile-drawer";
import { cn } from "@/lib/utils/cn";
import { PanelLeft } from "lucide-react";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import { useDesktop } from "@/lib/hooks/use-desktop";
import { UpdateBanner } from "./update-banner";
import { useChatStore } from "@/lib/stores/chat-store";
import { ThemeAmbientCanvas } from "@/components/theme/theme-ambient-canvas";
import { ThemeLCARSDecor }   from "@/components/theme/theme-lcars-decor";
import { AudioProvider } from "./AudioProvider";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { isMobile, isTablet } = useIsMobile();
  const { inDesktop, bridge } = useDesktop();
  const setDesktopLocalPath = useSettingsStore((s) => s.setDesktopLocalPath);
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const theme = useSettingsStore((s) => s.theme);
  const themeMode = useSettingsStore((s) => s.themeMode);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const persistedSidebarOpen = useSettingsStore((s) => s.sidebarOpen);
  const setPersistedSidebarOpen = useSettingsStore((s) => s.setSidebarOpen);
  const persistedSidebarSlim = useSettingsStore((s) => s.sidebarSlim);
  const setPersistedSidebarSlim = useSettingsStore((s) => s.setSidebarSlim);
  const navLayout = useSettingsStore((s) => s.navLayout);

  // Effective sidebar state: persisted preference on desktop, forced closed on
  // mobile/tablet (those use the drawer). Toggling on desktop writes through
  // to the store so the choice survives reloads.
  const sidebarOpen = isMobile || isTablet ? false : persistedSidebarOpen;
  const sidebarSlim = !isMobile && !isTablet && persistedSidebarSlim;
  const setSidebarOpen = (open: boolean) => {
    if (isMobile || isTablet) return; // desktop-only preference
    setPersistedSidebarOpen(open);
  };
  const setSidebarSlim = (slim: boolean) => {
    if (isMobile || isTablet) return;
    setPersistedSidebarSlim(slim);
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

    // All non-memex themes are self-contained (no light/dark mode variants).
    const NAMED_THEMES = new Set([
      "lcars", "lcars-blue", "lcars-teal", "cyberpunk",
      // Extended themes from Claude Design v1
      "shadowrun", "ops", "terminal", "hal9000", "nostromo",
      "tron", "bladerunner", "dune", "memex-archive",
    ]);

    // Legacy themes that have no CSS — coerce back to "memex".
    const LEGACY_THEMES = new Set(["amber", "ember", "slate", "signal", "office", "hacker", "star-trek", "minimal"]);

    // Self-heal: if a stale persisted legacy theme survived migration, reset.
    if (LEGACY_THEMES.has(theme) && !legacy) {
      setTheme("memex");
      return;
    }

    root.setAttribute("data-theme", theme);

    // Named themes don't have light/dark variants.
    if (NAMED_THEMES.has(theme)) {
      root.removeAttribute("data-mode");
      return;
    }

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

  // Desktop bridge — register native handlers when running in Memex Desktop app.
  // Mirrors the pattern claude.ai uses to detect window.claude.
  useEffect(() => {
    if (!inDesktop || !bridge) return;

    // Quick Entry window → pre-fill chat input and focus it
    bridge.onQuickSubmit((text) => {
      window.dispatchEvent(new CustomEvent("chat:prefill", { detail: text }));
    });

    // File type handler: .memex / .claude skill import
    (window as any).__memexImportFile = (filePath: string) => {
      window.dispatchEvent(new CustomEvent("memex:importFile", { detail: filePath }));
      router.push("/settings"); // navigate to settings where skills are managed
    };

    // Global shortcut: new conversation
    (window as any).__memexNewConversation = () => {
      const { createConversation, setActiveConversation } = useChatStore.getState();
      const id = createConversation();
      setActiveConversation(id);
      router.push("/chat");
    };

    // File/folder drag-drop from OS → set local path + navigate to dev workspace
    bridge.onOpenPath((path) => {
      setDesktopLocalPath(path);
      router.push("/dev");
    });
  }, [inDesktop, bridge, router]);

  // Stable callbacks — must not recreate on every render or MobileDrawer's
  // useEffect([pathname, onClose]) will fire and immediately close the drawer.
  const handleOpenDrawer = useCallback(() => setDrawerOpen(true), []);
  const handleCloseDrawer = useCallback(() => setDrawerOpen(false), []);

  const isTopBar = !isMobile && navLayout === "topbar";

  return (
    <div
      className="app-shell-root flex flex-col h-dvh bg-[var(--chat-bg,#0e1117)] text-[var(--chat-text,#e4e4e7)]"
      style={inDesktop ? { paddingTop: "40px" } : undefined}
    >
      {/* Ambient backgrounds & UI audio (Canvas + DOM overlays + SFX) */}
      <ThemeAmbientCanvas />
      {/* LCARS structural chrome — left arm strip + readout bars */}
      <ThemeLCARSDecor />
      <AudioProvider />
      {/* Desktop update banner — only visible when an update is ready */}
      <UpdateBanner />

      {/* Top Bar layout */}
      {isTopBar && <TopBar />}

      <div className={cn("flex flex-1 min-h-0", !isTopBar && "flex-row")}>
        {/* Desktop/Tablet Sidebar — hidden in topbar mode */}
        {!isMobile && !isTopBar && (
          <div
            className={cn(
              "transition-all duration-[220ms] ease-[cubic-bezier(0.22,1,0.36,1)] flex-shrink-0 overflow-hidden",
              sidebarOpen
                ? sidebarSlim ? "w-14" : "w-64"
                : "w-0"
            )}
          >
            <div className={cn("h-full", sidebarSlim ? "w-14" : "w-64")}>
              <Sidebar
                onCollapse={() => setSidebarSlim(true)}
                slim={sidebarSlim}
                onExpand={() => setSidebarSlim(false)}
              />
            </div>
          </div>
        )}

        {/* Main content */}
        <div
          className={cn(
            "relative flex-1 flex flex-col min-w-0 overflow-hidden",
            isMobile && "pb-[calc(3.5rem+env(safe-area-inset-bottom,0px))]"
          )}
          style={{
            ["--sidebar-rail-pad" as string]: !isMobile && !isTopBar && !sidebarOpen ? "2.75rem" : "0px",
          }}
        >
          {/* Edge-anchored expand handle — sidebar mode only, when fully hidden */}
          {!isMobile && !isTopBar && !sidebarOpen && (
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
      </div>

      {/* Mobile Bottom Tab Bar */}
      {isMobile && <BottomTabBar onMenuPress={handleOpenDrawer} />}

      {/* Mobile Drawer */}
      {isMobile && <MobileDrawer open={drawerOpen} onClose={handleCloseDrawer} />}
    </div>
  );
}
