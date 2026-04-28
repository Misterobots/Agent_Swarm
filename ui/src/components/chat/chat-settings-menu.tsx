"use client";

import { useState, useRef, useEffect } from "react";
import { Settings2, Brain } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { ThemeSelector } from "./theme-selector";
import { UltraplanToggle } from "./ultraplan-toggle";
import { UltrathinkToggle } from "./ultrathink-toggle";
import { WebGroundingToggle } from "./web-grounding-toggle";
import { DocGroundingToggle } from "./doc-grounding-toggle";
import { FileGroundingToggle } from "./file-grounding-toggle";
import { SwarmToggle } from "./swarm-toggle";
import { useChatStore } from "@/lib/stores/chat-store";

export function ChatSettingsMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const updateConversation = useChatStore((s) => s.updateConversation);
  const activeConv = useChatStore((s) =>
    s.activeConversationId ? s.conversations[s.activeConversationId] : null
  );

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
          "flex-shrink-0 w-9 h-9 md:w-10 md:h-10 rounded-md flex items-center justify-center transition-colors",
          isOpen
            ? "bg-[var(--chat-accent)] text-white"
            : "bg-[var(--chat-panel)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] border border-[var(--chat-border)]"
        )}
        title="Chat settings"
      >
        <Settings2 size={16} />
      </button>

      {/* Settings menu dropdown */}
      {isOpen && (
        <div className="absolute bottom-full right-0 mb-2 w-64 rounded-lg border border-[var(--chat-border)] bg-[var(--chat-surface)] shadow-lg p-3 space-y-3 z-30 max-h-[70vh] overflow-y-auto scrollbar-thin">
          <div className="text-xs font-semibold text-[var(--chat-muted)] uppercase tracking-wide mb-2">
            Chat Settings
          </div>

          {/* Theme */}
          <div className="space-y-1.5">
            <label className="text-xs text-[var(--chat-muted)]">Theme</label>
            <ThemeSelector />
          </div>

          {/* Modes */}
          <div className="space-y-2">
            <label className="text-xs text-[var(--chat-muted)]">Modes</label>
            <div className="space-y-1.5">
              <UltraplanToggle />
              <UltrathinkToggle />
              <SwarmToggle />
            </div>
          </div>

          {/* Grounding */}
          <div className="space-y-2">
            <label className="text-xs text-[var(--chat-muted)]">Grounding</label>
            <div className="space-y-1.5">
              <WebGroundingToggle />
              <DocGroundingToggle />
              <FileGroundingToggle />
            </div>
          </div>

          {/* Memory toggle */}
          {activeConversationId && (
            <div className="space-y-2 pt-2 border-t border-[var(--chat-border)]">
              <button
                type="button"
                onClick={() => {
                  updateConversation(activeConversationId, {
                    memoryEnabled: !(activeConv?.memoryEnabled ?? false),
                  });
                }}
                className={cn(
                  "w-full inline-flex items-center gap-2 px-3 py-2 rounded-md text-xs border transition-colors",
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
