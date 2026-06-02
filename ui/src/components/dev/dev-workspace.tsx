"use client";

import { ChatView } from "@/components/chat/chat-view";
import { TabbedEditor } from "./tabbed-editor";
import { TabbedTerminal } from "./tabbed-terminal";
import { PreviewCanvas } from "./preview-canvas";
import { QuickActionsToolbar } from "./quick-actions-toolbar";
import { Code2, Eye, FileCode, Monitor, Terminal, X, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import { useDevStore } from "@/lib/stores/dev-store";
import { IconButton } from "@/components/ui";
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

  if (isMobile) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4 p-6 text-center">
        <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-[var(--chat-panel)] border border-[var(--chat-border)]">
          <Monitor size={22} className="text-[var(--chat-muted)]" />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium text-[var(--chat-text)]">Dev workspace is desktop-only</p>
          <p className="text-xs text-[var(--chat-muted)] max-w-[260px]">
            Open Memex on a desktop browser to use the editor, terminal, and agent tools.
          </p>
        </div>
        <button
          onClick={() => router.push("/chat")}
          className="px-4 py-2 text-xs font-medium rounded-md bg-[var(--chat-panel)] border border-[var(--chat-border)] text-[var(--chat-text)] hover:text-[var(--chat-accent)] transition-colors"
        >
          Go to Chat →
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Quick Actions Toolbar */}
      <QuickActionsToolbar />

      {/* View Mode + Panel Controls */}
      <div className="relative flex items-center gap-3 bg-[var(--chat-surface)] px-4 py-2">
        <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />

        <div className="ml-auto flex items-center gap-1.5">
          <ToolbarButton
            onClick={() => router.push("/dev/pioneers")}
            title="Pioneer Academy — build your team"
            icon={<Users size={14} />}
            label="Pioneers"
          />
          <ToolbarButton
            onClick={toggleEditorPanel}
            active={showEditorPanel}
            title={showEditorPanel ? "Hide editor" : "Show editor"}
            icon={<FileCode size={14} />}
            label="Editor"
          />
          <ToolbarButton
            onClick={toggleTerminalPanel}
            active={showTerminalPanel}
            title={showTerminalPanel ? "Hide terminal" : "Show terminal"}
            icon={<Terminal size={14} />}
            label="Terminal"
          />
        </div>
        <div className="absolute bottom-0 left-0 right-0 divider" />
      </div>

      {/* Main Workspace with Flyout Panels */}
      <div className="flex-1 overflow-hidden relative">
        {/* Primary Content: Chat or Preview */}
        <div className="h-full w-full">
          {viewMode === "preview" ? <PreviewCanvas /> : <ChatView showDevContext />}
        </div>

        {/* Editor Flyout (right) */}
        {showEditorPanel && (
          <FlyoutSurface
            position="right"
            className="w-[50%]"
            title="Code Editor"
            icon={<FileCode size={14} />}
            onClose={() => setShowEditorPanel(false)}
          >
            <TabbedEditor />
          </FlyoutSurface>
        )}

        {/* Terminal Flyout (bottom) */}
        {showTerminalPanel && (
          <FlyoutSurface
            position="bottom"
            className={cn("h-[40%]", showEditorPanel && "right-[50%]")}
            title="Terminal"
            icon={<Terminal size={14} />}
            onClose={() => setShowTerminalPanel(false)}
          >
            <TabbedTerminal />
          </FlyoutSurface>
        )}
      </div>
    </div>
  );
}

function ViewModeToggle({
  viewMode,
  onChange,
}: {
  viewMode: "code" | "preview";
  onChange: (m: "code" | "preview") => void;
}) {
  return (
    <div
      className="inline-flex items-center gap-1 p-1 rounded-md border border-[var(--chat-border)] bg-[var(--chat-panel)]"
      style={{ boxShadow: "var(--elev-1), inset 0 1px 2px rgba(0,0,0,0.08)" }}
      role="tablist"
    >
      <SegmentButton
        active={viewMode === "code"}
        onClick={() => onChange("code")}
        icon={<Code2 size={13} />}
        label="Code"
      />
      <SegmentButton
        active={viewMode === "preview"}
        onClick={() => onChange("preview")}
        icon={<Eye size={13} />}
        label="Preview"
      />
    </div>
  );
}

function SegmentButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-3 py-1 text-[12px] font-medium transition-all",
        active
          ? "bg-[var(--chat-elevated)] text-[var(--chat-text)]"
          : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
      )}
      style={active ? { boxShadow: "var(--elev-1)" } : undefined}
    >
      <span className={active ? "text-[var(--chat-accent)]" : ""}>{icon}</span>
      {label}
    </button>
  );
}

function ToolbarButton({
  onClick,
  active = false,
  title,
  icon,
  label,
}: {
  onClick: () => void;
  active?: boolean;
  title: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] font-medium rounded-md transition-colors border",
        active
          ? "bg-[var(--chat-accent-soft)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] border-[var(--chat-border)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_50%,var(--chat-text))]"
      )}
    >
      <span className={active ? "text-[var(--chat-accent)]" : ""}>{icon}</span>
      {label}
    </button>
  );
}

function FlyoutSurface({
  position,
  className,
  title,
  icon,
  onClose,
  children,
}: {
  position: "right" | "bottom";
  className?: string;
  title: string;
  icon: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const base = position === "right"
    ? "absolute top-0 right-0 h-full"
    : "absolute bottom-0 left-0 right-0";
  const borderSide = position === "right"
    ? "border-l border-[var(--chat-border)]"
    : "border-t border-[var(--chat-border)]";

  return (
    <div
      className={cn(base, borderSide, "bg-[var(--chat-surface)] z-20 flex flex-col", className)}
      style={{ boxShadow: "var(--elev-3)" }}
    >
      <div
        className="relative flex items-center justify-between px-4 py-2 bg-[var(--chat-surface)]"
        style={{ borderBottom: "1px solid var(--chat-border)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <div
            className="w-6 h-6 rounded-sm flex items-center justify-center text-[var(--chat-accent)]"
            style={{
              background: "var(--chat-accent-soft)",
              border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
            }}
          >
            {icon}
          </div>
          <span className="text-[13px] font-semibold text-[var(--chat-text)]">{title}</span>
        </div>
        <IconButton
          label={`Close ${title}`}
          icon={<X size={14} />}
          onClick={onClose}
          variant="ghost"
          size="sm"
          onMouseDown={(e) => e.stopPropagation()}
        />
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  );
}
