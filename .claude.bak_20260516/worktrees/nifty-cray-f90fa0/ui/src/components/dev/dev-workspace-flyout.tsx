"use client";

import { useState, useEffect } from "react";
import { ChatView } from "@/components/chat/chat-view";
import { TabbedEditor } from "./tabbed-editor";
import { TabbedTerminal } from "./tabbed-terminal";
import { PreviewCanvas } from "./preview-canvas";
import { QuickActionsToolbar } from "./quick-actions-toolbar";
import { Code2, Eye, FileCode, Terminal, X, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import { useDevStore } from "@/lib/stores/dev-store";
import { cn } from "@/lib/utils/cn";

export function DevWorkspace() {
  const { isMobile } = useIsMobile();
  const router = useRouter();
  const { 
    viewMode, 
    setViewMode,
    showEditorPanel,
    showTerminalPanel,
    toggleEditorPanel,
    toggleTerminalPanel,
    setShowEditorPanel,
    setShowTerminalPanel,
  } = useDevStore();

  // Redirect to chat on mobile — Dev workspace is desktop-only
  useEffect(() => {
    if (isMobile) router.replace("/chat");
  }, [isMobile, router]);

  if (isMobile) return null;

  return (
    <div className="flex flex-col h-full">
      {/* Quick Actions Toolbar */}
      <QuickActionsToolbar />

      {/* View Mode Toggle & Panel Controls */}
      <div className="flex items-center gap-2 px-4 py-2 bg-[var(--chat-surface)] border-b border-[var(--chat-border)]">
        <span className="text-xs text-[var(--chat-muted)] mr-2">View:</span>
        <div className="flex items-center gap-1 bg-[var(--chat-input-bg)] rounded p-0.5">
          <button
            onClick={() => setViewMode("code")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors",
              viewMode === "code"
                ? "bg-[var(--chat-accent)] text-white"
                : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
            )}
            title="Code view (editor + terminal)"
          >
            <Code2 size={14} />
            Code
          </button>
          <button
            onClick={() => setViewMode("preview")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors",
              viewMode === "preview"
                ? "bg-[var(--chat-accent)] text-white"
                : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
            )}
            title="Preview mode (live output)"
          >
            <Eye size={14} />
            Preview
          </button>
        </div>

        {/* Flyout Panel Toggles */}
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => router.push("/dev/pioneers")}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors text-[var(--chat-muted)] hover:text-[var(--chat-text)] border border-[var(--chat-border)]"
            title="Pioneer Academy - Build Your Team"
          >
            <Users size={14} />
            Pioneers
          </button>
          <button
            onClick={toggleEditorPanel}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors",
              showEditorPanel
                ? "bg-[var(--chat-accent)] text-white"
                : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] border border-[var(--chat-border)]"
            )}
            title={showEditorPanel ? "Hide Editor" : "Show Editor"}
          >
            <FileCode size={14} />
            Editor
          </button>
          <button
            onClick={toggleTerminalPanel}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors",
              showTerminalPanel
                ? "bg-[var(--chat-accent)] text-white"
                : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] border border-[var(--chat-border)]"
            )}
            title={showTerminalPanel ? "Hide Terminal" : "Show Terminal"}
          >
            <Terminal size={14} />
            Terminal
          </button>
        </div>
      </div>

      {/* Main Workspace with Flyout Panels */}
      <div className="flex-1 overflow-hidden relative">
        {/* Primary Content: Chat or Preview */}
        <div className="h-full w-full">
          {viewMode === "preview" ? (
            <PreviewCanvas />
          ) : (
            <ChatView showDevContext />
          )}
        </div>

        {/* Editor Flyout Panel (Right Side) */}
        {showEditorPanel && (
          <div
            className={cn(
              "absolute top-0 right-0 h-full bg-[var(--chat-surface)] border-l border-[var(--chat-border)] shadow-2xl z-20",
              "w-[50%]"
            )}
          >
            <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--chat-border)] bg-[var(--chat-input-bg)] relative z-30">
              <div className="flex items-center gap-2">
                <FileCode size={16} className="text-[var(--chat-accent)]" />
                <span className="text-sm font-medium">Code Editor</span>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowEditorPanel(false);
                }}
                className="p-1 hover:bg-[var(--chat-hover)] rounded transition-colors"
                title="Close Editor"
              >
                <X size={16} />
              </button>
            </div>
            <div className="h-[calc(100%-40px)]">
              <TabbedEditor />
            </div>
          </div>
        )}

        {/* Terminal Flyout Panel (Bottom) */}
        {showTerminalPanel && (
          <div
            className={cn(
              "absolute bottom-0 left-0 right-0 bg-[var(--chat-surface)] border-t border-[var(--chat-border)] shadow-2xl transition-transform duration-300 ease-in-out z-20",
              "h-[40%]",
              showEditorPanel && "right-[50%]" // Adjust width when editor is open
            )}
          >
            <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--chat-border)] bg-[var(--chat-input-bg)] relative z-30">
              <div className="flex items-center gap-2">
                <Terminal size={16} className="text-[var(--chat-accent)]" />
                <span className="text-sm font-medium">Terminal</span>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowTerminalPanel(false);
                }}
                className="p-1 hover:bg-[var(--chat-hover)] rounded transition-colors"
                title="Close Terminal"
              >
                <X size={16} />
              </button>
            </div>
            <div className="h-[calc(100%-40px)]">
              <TabbedTerminal />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
