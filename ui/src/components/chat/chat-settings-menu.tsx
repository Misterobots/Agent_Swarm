"use client";

import { useState, useRef, useEffect } from "react";
import { Settings2, Brain, Moon, Sun, Monitor, Tv2 } from "lucide-react";
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

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  return (
    <div className="relative" ref={menuRef}>
      {/* Settings button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
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

      {/* Settings menu dropdown */}
      {isOpen && (
        <div
          className="absolute bottom-full right-0 mb-2 w-56 rounded-md border border-[var(--chat-border)] bg-[var(--chat-elevated)] p-2.5 space-y-2 z-30 max-h-[55vh] overflow-y-auto scrollbar-thin theme-picker-enter"
          style={{ boxShadow: "var(--elev-3)" }}
        >
          <div className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wide mb-1">
            Chat Settings
          </div>

          {/* Theme — inline buttons, no nested dropdown */}
          <div className="space-y-1.5">
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

          {/* Quality/Effort Settings */}
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
      )}
    </div>
  );
}

/** Compact inline theme picker — no nested dropdown, safe inside other menus. */
function ThemeInline() {
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const themeMode = useSettingsStore((s) => s.themeMode);
  const setThemeMode = useSettingsStore((s) => s.setThemeMode);

  const isLcars = theme === "lcars";

  const modes: Array<{ id: ThemeMode; icon: React.ReactNode; label: string }> = [
    { id: "system", icon: <Monitor size={12} />, label: "System" },
    { id: "dark",   icon: <Moon size={12} />,    label: "Dark"   },
    { id: "light",  icon: <Sun size={12} />,     label: "Light"  },
  ];

  return (
    <div className="space-y-1.5">
      {/* Memex modes row */}
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
      {/* Named themes row */}
      <button
        type="button"
        onClick={() => setTheme("lcars")}
        className={cn(
          "w-full inline-flex items-center gap-2 px-2 py-1.5 text-[11px] rounded-sm border transition-colors",
          isLcars
            ? "bg-[var(--chat-accent-soft)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] text-[var(--chat-accent-strong)]"
            : "bg-[var(--chat-panel)] border-[var(--chat-border)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
        )}
      >
        <Tv2 size={12} className={isLcars ? "text-[var(--chat-accent)]" : ""} />
        <span>LCARS</span>
        {isLcars && <span className="ml-auto text-[var(--chat-accent)] text-[10px]">✓</span>}
      </button>
    </div>
  );
}
