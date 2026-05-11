"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Settings2, Brain, Moon, Sun, Monitor } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { ResearchToggle } from "./research-toggle";
import { UltraplanToggle } from "./ultraplan-toggle";
import { UltrathinkToggle } from "./ultrathink-toggle";
import { WebGroundingToggle } from "./web-grounding-toggle";
import { DocGroundingToggle } from "./doc-grounding-toggle";
import { FileGroundingToggle } from "./file-grounding-toggle";
import { SwarmToggle } from "./swarm-toggle";
import { DesignModeToggle } from "./design-mode-toggle";
import { QualitySettingsPanel } from "./quality-settings-panel";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore, type ThemeMode } from "@/lib/stores/settings-store";

export function ChatSettingsMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ bottom: 0, right: 0, maxHeight: "70vh" });
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const updateConversation = useChatStore((s) => s.updateConversation);
  const activeConv = useChatStore((s) => s.activeConversation());

  const ultraplanMode = useSettingsStore((s) => s.ultraplanMode);
  const ultrathinkMode = useSettingsStore((s) => s.ultrathinkMode);
  const researchMode = useSettingsStore((s) => s.researchMode);
  const swarmMode = useSettingsStore((s) => s.swarmMode);
  const groundingWeb = useSettingsStore((s) => s.groundingWeb);
  const groundingDocs = useSettingsStore((s) => s.groundingDocs);
  const groundingFile = useSettingsStore((s) => s.groundingFile);
  const anyModeActive = ultraplanMode || ultrathinkMode || researchMode || swarmMode || groundingWeb || groundingDocs || groundingFile;

  const updatePos = useCallback(() => {
    if (!btnRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    // Clamp maxHeight so menu never overflows the top of the viewport
    const spaceAbove = r.top - 16;
    setMenuPos({
      bottom: window.innerHeight - r.top + 8,
      right: window.innerWidth - r.right,
      maxHeight: `${Math.min(spaceAbove, window.innerHeight * 0.7)}px`,
    });
  }, []);

  const open = () => {
    updatePos();
    setIsOpen(true);
  };

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (
        btnRef.current?.contains(e.target as Node) ||
        menuRef.current?.contains(e.target as Node)
      ) return;
      setIsOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isOpen]);

  // Close on scroll/resize
  useEffect(() => {
    if (!isOpen) return;
    const handler = () => setIsOpen(false);
    window.addEventListener("scroll", handler, true);
    window.addEventListener("resize", handler);
    return () => {
      window.removeEventListener("scroll", handler, true);
      window.removeEventListener("resize", handler);
    };
  }, [isOpen]);

  const dropdown = isOpen ? (
    <div
      ref={menuRef}
      className="fixed w-56 rounded-md border border-[var(--chat-border)] bg-[var(--chat-elevated)] p-2 space-y-1.5 z-[9999] overflow-y-auto scrollbar-thin theme-picker-enter"
      style={{
        bottom: menuPos.bottom,
        right: menuPos.right,
        maxHeight: menuPos.maxHeight,
        boxShadow: "var(--elev-3)",
      }}
    >
      <div className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wide mb-1">
        Chat Settings
      </div>

      {/* Theme */}
      <div className="space-y-1">
        <label className="text-xs text-[var(--chat-muted)]">Theme</label>
        <ThemeInline />
      </div>

      {/* Modes */}
      <div className="space-y-1 pt-1.5 border-t border-[var(--chat-border)]">
        <label className="text-xs text-[var(--chat-muted)]">Modes</label>
        <div className="grid grid-cols-2 gap-1">
          <ResearchToggle />
          <UltraplanToggle />
          <UltrathinkToggle />
          <SwarmToggle />
          <DesignModeToggle />
        </div>
      </div>

      {/* Grounding */}
      <div className="space-y-1 pt-1.5 border-t border-[var(--chat-border)]">
        <label className="text-xs text-[var(--chat-muted)]">Grounding</label>
        <div className="grid grid-cols-2 gap-1">
          <WebGroundingToggle />
          <DocGroundingToggle />
          <FileGroundingToggle />
        </div>
      </div>

      {/* Quality/Effort */}
      <div className="space-y-1 pt-1.5 border-t border-[var(--chat-border)]">
        <label className="text-xs text-[var(--chat-muted)]">Quality & Effort</label>
        <QualitySettingsPanel />
      </div>

      {/* Memory toggle */}
      {activeConversationId && (
        <div className="space-y-1 pt-1.5 border-t border-[var(--chat-border)]">
          <button
            type="button"
            onClick={() => {
              updateConversation(activeConversationId, {
                memoryEnabled: !(activeConv?.memoryEnabled ?? false),
              });
            }}
            className={cn(
              "w-full inline-flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs border transition-colors",
              activeConv?.memoryEnabled
                ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
                : "bg-[var(--chat-panel)] text-[var(--chat-muted)] border-[var(--chat-border)] hover:text-[var(--chat-text)]"
            )}
            title="Toggle cross-session memory recall"
          >
            <Brain size={14} />
            <span className="flex-1 text-left">Memory</span>
            <span className="text-xs opacity-70">
              {activeConv?.memoryEnabled ? "On" : "Off"}
            </span>
          </button>
        </div>
      )}
    </div>
  ) : null;

  return (
    <div className="relative">
      <button
        ref={btnRef}
        type="button"
        onClick={open}
        className={cn(
          "flex-shrink-0 w-9 h-9 md:w-10 md:h-10 rounded-md flex items-center justify-center transition-colors relative",
          isOpen
            ? "bg-[var(--chat-accent)] text-white"
            : anyModeActive
              ? "bg-[color:color-mix(in_srgb,var(--chat-accent-2)_15%,var(--chat-panel))] text-[var(--chat-accent-2)] border border-[color:color-mix(in_srgb,var(--chat-accent-2)_50%,var(--chat-border))]"
              : "bg-[var(--chat-panel)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] border border-[var(--chat-border)]"
        )}
        title={anyModeActive ? "Chat settings (modes active)" : "Chat settings"}
      >
        <Settings2 size={16} />
        {anyModeActive && !isOpen && (
          <span className="absolute top-0.5 right-0.5 w-2 h-2 rounded-full bg-[var(--chat-accent-2)]" />
        )}
      </button>

      {typeof window !== "undefined" && createPortal(dropdown, document.body)}
    </div>
  );
}

/** Compact inline theme picker — no nested dropdown. */
function ThemeInline() {
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const themeMode = useSettingsStore((s) => s.themeMode);
  const setThemeMode = useSettingsStore((s) => s.setThemeMode);

  const modes: Array<{ id: ThemeMode; icon: React.ReactNode; label: string }> = [
    { id: "system", icon: <Monitor size={11} />, label: "System" },
    { id: "dark",   icon: <Moon size={11} />,    label: "Dark"   },
    { id: "light",  icon: <Sun size={11} />,     label: "Light"  },
  ];

  const lcarsVariants: Array<{ id: string; label: string; dot: string }> = [
    { id: "lcars",       label: "Amber", dot: "#FFAA00" },
    { id: "lcars-blue",  label: "Blue",  dot: "#5577FF" },
    { id: "lcars-teal",  label: "Teal",  dot: "#00CC77" },
  ];

  return (
    <div className="space-y-1">
      <div className="flex gap-1">
        {modes.map((m) => {
          const active = theme === "memex" && themeMode === m.id;
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => { setTheme("memex"); setThemeMode(m.id); }}
              className={cn(
                "flex-1 inline-flex items-center justify-center gap-1 py-1 text-[11px] rounded-sm border transition-colors",
                active
                  ? "bg-[var(--chat-accent-soft)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] text-[var(--chat-accent-strong)]"
                  : "bg-[var(--chat-panel)] border-[var(--chat-border)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
              )}
            >
              {m.icon}
              <span>{m.label}</span>
            </button>
          );
        })}
      </div>
      <div className="flex gap-1">
        {lcarsVariants.map((v) => {
          const active = theme === v.id;
          return (
            <button
              key={v.id}
              type="button"
              onClick={() => setTheme(v.id as typeof theme)}
              className={cn(
                "flex-1 inline-flex items-center justify-center gap-1.5 py-1 text-[11px] rounded-sm border transition-colors",
                active
                  ? "bg-[var(--chat-accent-soft)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] text-[var(--chat-accent-strong)]"
                  : "bg-[var(--chat-panel)] border-[var(--chat-border)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
              )}
            >
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: v.dot }} />
              <span>{v.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
