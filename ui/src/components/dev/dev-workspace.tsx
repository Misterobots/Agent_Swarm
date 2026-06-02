"use client";

import type { ReactNode } from "react";
import { ChatView } from "@/components/chat/chat-view";
import { TabbedEditor } from "./tabbed-editor";
import { TabbedTerminal } from "./tabbed-terminal";
import { PreviewCanvas } from "./preview-canvas";
import { QuickActionsToolbar } from "./quick-actions-toolbar";
import { Code2, Eye, FileCode, Terminal, X, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import { useDevStore } from "@/lib/stores/dev-store";
import { useDevPanelStore } from "@/lib/stores/dev-panel-store";
import { IconButton } from "@/components/ui";
import { cn } from "@/lib/utils/cn";
import { registerPanel, getRegisteredPanels, type PanelRegistration } from "./dev-panels-registry";
import { ProjectSwitcher } from "./project-switcher";
import { MobileDevView } from "./mobile-dev-view";
import "./goals-panel"; // register Goals panel (side-effect)
import "./notes-panel"; // register Notes panel (side-effect)

// ---------------------------------------------------------------------------
// Built-in panel registrations (Editor + Terminal)
// These run once at module scope — duplicate calls are ignored.
// ---------------------------------------------------------------------------
registerPanel({
  id: "editor",
  title: "Code Editor",
  position: "right",
  toolbarOrder: 10,
  className: "w-[50%]",
  icon: <FileCode size={14} />,
  component: TabbedEditor,
});

registerPanel({
  id: "terminal",
  title: "Terminal",
  position: "bottom",
  toolbarOrder: 20,
  icon: <Terminal size={14} />,
  component: TabbedTerminal,
});

export function DevWorkspace() {
  const { isMobile } = useIsMobile();
  const router = useRouter();
  const {
    viewMode,
    setViewMode,
    showEditorPanel,
    showTerminalPanel,
    togglePanel,
    setShowEditorPanel,
    setShowTerminalPanel,
  } = useDevPanelStore();

  if (isMobile) {
    return <MobileDevView />;
  }

  const panels = getRegisteredPanels();

  // Map panel id → current show state (falls back to legacy booleans for
  // editor/terminal so they stay in sync with persisted flags).
  function isPanelVisible(panel: PanelRegistration): boolean {
    if (panel.id === "editor") return showEditorPanel;
    if (panel.id === "terminal") return showTerminalPanel;
    // For registry-only panels use the generic showPanel record
    const panelStore = useDevPanelStore.getState();
    return panelStore.showPanel[panel.id] ?? false;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Quick Actions Toolbar */}
      <QuickActionsToolbar />

      {/* View Mode + Panel Controls */}
      <div className="relative flex items-center gap-3 bg-[var(--chat-surface)] px-4 py-2">
        <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />

        <div className="ml-auto flex items-center gap-1.5">
          {/* Project switcher */}
          <ProjectSwitcher />

          {/* Divider */}
          <div className="w-px h-4 bg-[var(--chat-border)]" />

          {/* Pioneers — not a flyout panel, kept as a hardcoded button */}
          <ToolbarButton
            onClick={() => router.push("/dev/pioneers")}
            title="Pioneer Academy — build your team"
            icon={<Users size={14} />}
            label="Pioneers"
          />

          {/* Registry-driven panel toggle buttons */}
          {panels.map((panel) => (
            <ToolbarButton
              key={panel.id}
              onClick={() => togglePanel(panel.id)}
              active={isPanelVisible(panel)}
              title={
                isPanelVisible(panel)
                  ? `Hide ${panel.title.toLowerCase()}`
                  : `Show ${panel.title.toLowerCase()}`
              }
              icon={panel.icon}
              label={panel.title}
            />
          ))}
        </div>
        <div className="absolute bottom-0 left-0 right-0 divider" />
      </div>

      {/* Main Workspace with Flyout Panels */}
      <div className="flex-1 overflow-hidden relative">
        {/* Primary Content: Chat or Preview */}
        <div className="h-full w-full">
          {viewMode === "preview" ? <PreviewCanvas /> : <ChatView showDevContext />}
        </div>

        {/* Registry-driven flyout surfaces */}
        {panels.map((panel) => {
          if (!isPanelVisible(panel)) return null;

          // Terminal flyout narrows when the editor is also open
          const extraClass =
            panel.id === "terminal" && showEditorPanel ? "right-[50%]" : undefined;

          const closePanel =
            panel.id === "editor"
              ? () => setShowEditorPanel(false)
              : panel.id === "terminal"
              ? () => setShowTerminalPanel(false)
              : () => togglePanel(panel.id);

          return (
            <FlyoutSurface
              key={panel.id}
              position={panel.position}
              className={cn(
                panel.id === "terminal" && "h-[40%]",
                panel.className,
                extraClass
              )}
              title={panel.title}
              icon={panel.icon}
              onClose={closePanel}
            >
              <panel.component />
            </FlyoutSurface>
          );
        })}
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
  icon: ReactNode;
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
  icon: ReactNode;
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
  icon: ReactNode;
  onClose: () => void;
  children: ReactNode;
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
