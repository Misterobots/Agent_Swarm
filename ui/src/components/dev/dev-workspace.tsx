"use client";

import type { ReactNode } from "react";
import { useRef, useCallback, useState } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { ChatView } from "@/components/chat/chat-view";
import { TabbedEditor } from "./tabbed-editor";
import { TabbedTerminal } from "./tabbed-terminal";
import { PreviewCanvas } from "./preview-canvas";
import { Code2, Eye, FileCode, Terminal, X, Users2, Pin, PinOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import { useDevPanelStore } from "@/lib/stores/dev-panel-store";
import { useChatStore } from "@/lib/stores/chat-store";
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
  title: "Editor",
  position: "right",
  toolbarOrder: 10,
  // No className — width controlled by the resizable Panel component
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

// ---------------------------------------------------------------------------
// Resize handle style constants
// ---------------------------------------------------------------------------
const HORZ_HANDLE_CLASS =
  "w-[3px] flex-shrink-0 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors duration-150 cursor-ew-resize";

const VERT_HANDLE_CLASS =
  "h-[3px] flex-shrink-0 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors duration-150 cursor-ns-resize";

// ---------------------------------------------------------------------------
// DevWorkspace
// ---------------------------------------------------------------------------

export function DevWorkspace() {
  const { isMobile } = useIsMobile();
  const router = useRouter();
  const {
    viewMode,
    setViewMode,
    showEditorPanel,
    showTerminalPanel,
    showPanel,
    togglePanel,
    setShowEditorPanel,
    setShowTerminalPanel,
    panelDocked,
    setPanelDocked,
  } = useDevPanelStore();

  const sessionFileChangeCount = useChatStore((s) => {
    const conv = s.conversations.find((c) => c.id === s.activeConversationId);
    if (!conv) return 0;
    const paths = new Set<string>();
    for (const msg of conv.messages) {
      for (const fc of msg.fileChanges ?? []) paths.add(fc.path);
    }
    return paths.size;
  });

  if (isMobile) return <MobileDevView />;

  const panels = getRegisteredPanels();

  function isPanelVisible(panel: PanelRegistration): boolean {
    if (panel.id === "editor") return showEditorPanel;
    if (panel.id === "terminal") return showTerminalPanel;
    return showPanel[panel.id] ?? false;
  }

  // Default: docked. Only floating if explicitly set to false.
  function isPanelDocked(id: string): boolean {
    return panelDocked[id] ?? true;
  }

  function closeFn(panel: PanelRegistration): () => void {
    if (panel.id === "editor") return () => setShowEditorPanel(false);
    if (panel.id === "terminal") return () => setShowTerminalPanel(false);
    return () => togglePanel(panel.id);
  }

  const visible = panels.filter((p) => isPanelVisible(p));
  const dockedRight = visible.filter((p) => p.position === "right" && isPanelDocked(p.id));
  const dockedBottom = visible.filter((p) => p.position === "bottom" && isPanelDocked(p.id));
  const floating = visible.filter((p) => !isPanelDocked(p.id));

  const mainContent = viewMode === "preview" ? <PreviewCanvas /> : <ChatView showDevContext />;

  // ---------------------------------------------------------------------------
  // Build horizontal Group children as an array so Separator + Panel pairs
  // sit as direct children without Fragment wrappers.
  // ---------------------------------------------------------------------------
  const horzChildren: ReactNode[] = [
    <Panel key="main" id="workspace-main" minSize={20}>
      <div className="h-full overflow-hidden">{mainContent}</div>
    </Panel>,
  ];
  for (const panel of dockedRight) {
    horzChildren.push(
      <Separator key={`sep-r-${panel.id}`} className={HORZ_HANDLE_CLASS} />,
      <Panel key={panel.id} id={`ws-r-${panel.id}`} defaultSize={40} minSize={15}>
        <DockedSurface
          position="right"
          title={panel.title}
          icon={panel.icon}
          onClose={closeFn(panel)}
          onFloat={() => setPanelDocked(panel.id, false)}
        >
          <panel.component />
        </DockedSurface>
      </Panel>
    );
  }

  // ---------------------------------------------------------------------------
  // Build vertical Group children similarly.
  // ---------------------------------------------------------------------------
  const vertChildren: ReactNode[] = [
    <Panel key="top" id="workspace-top" minSize={15}>
      <Group orientation="horizontal" className="h-full" id="dev-h">
        {horzChildren}
      </Group>
    </Panel>,
  ];
  for (const panel of dockedBottom) {
    vertChildren.push(
      <Separator key={`sep-b-${panel.id}`} className={VERT_HANDLE_CLASS} />,
      <Panel key={panel.id} id={`ws-b-${panel.id}`} defaultSize={30} minSize={10}>
        <DockedSurface
          position="bottom"
          title={panel.title}
          icon={panel.icon}
          onClose={closeFn(panel)}
          onFloat={() => setPanelDocked(panel.id, false)}
        >
          <panel.component />
        </DockedSurface>
      </Panel>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* ----------------------------------------------------------------- */}
      {/* Toolbar                                                             */}
      {/* ----------------------------------------------------------------- */}
      <div className="relative flex items-center gap-3 bg-[var(--chat-surface)] px-4 py-2">
        <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />

        <ToolbarButton
          onClick={() => router.push("/dev/pioneers")}
          title="Agent Team — manage your pioneer agents"
          icon={<Users2 size={14} />}
          label="Agent Team"
        />

        <div className="ml-auto flex items-center gap-1.5">
          <ProjectSwitcher />
          <div className="w-px h-4 bg-[var(--chat-border)]" />
          {panels.map((panel) => (
            <ToolbarButton
              key={panel.id}
              onClick={() => togglePanel(panel.id)}
              active={isPanelVisible(panel)}
              title={isPanelVisible(panel) ? `Hide ${panel.title.toLowerCase()}` : `Show ${panel.title.toLowerCase()}`}
              icon={panel.icon}
              label={panel.title}
              badge={panel.id === "editor" && sessionFileChangeCount > 0 ? sessionFileChangeCount : undefined}
            />
          ))}
        </div>
        <div className="absolute bottom-0 left-0 right-0 divider" />
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Main workspace — docked panels in resizable Groups                 */}
      {/* ----------------------------------------------------------------- */}
      <div className="flex-1 overflow-hidden relative">
        <Group orientation="vertical" className="h-full" id="dev-v">
          {vertChildren}
        </Group>

        {/* Floating overlay panels */}
        {floating.map((panel) => (
          <FlyoutSurface
            key={panel.id}
            position={panel.position}
            title={panel.title}
            icon={panel.icon}
            onClose={closeFn(panel)}
            onDock={() => setPanelDocked(panel.id, true)}
          >
            <panel.component />
          </FlyoutSurface>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DockedSurface — renders inside the resizable layout
// ---------------------------------------------------------------------------

function DockedSurface({
  position,
  title,
  icon,
  onClose,
  onFloat,
  children,
}: {
  position: "right" | "bottom";
  title: string;
  icon: ReactNode;
  onClose: () => void;
  onFloat: () => void;
  children: ReactNode;
}) {
  const borderClass =
    position === "right"
      ? "border-l border-[var(--chat-border)]"
      : "border-t border-[var(--chat-border)]";

  return (
    <div className={cn("h-full flex flex-col bg-[var(--chat-surface)]", borderClass)}>
      <div
        className="flex items-center justify-between px-4 py-2 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--chat-border)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <div
            className="w-6 h-6 rounded-sm flex-shrink-0 flex items-center justify-center text-[var(--chat-accent)]"
            style={{
              background: "var(--chat-accent-soft)",
              border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
            }}
          >
            {icon}
          </div>
          <span className="text-[13px] font-semibold text-[var(--chat-text)] truncate">{title}</span>
        </div>
        <div className="flex items-center gap-0.5 flex-shrink-0">
          <IconButton
            label="Pop out panel"
            icon={<PinOff size={13} />}
            onClick={onFloat}
            variant="ghost"
            size="sm"
            title="Float as overlay"
          />
          <IconButton
            label={`Close ${title}`}
            icon={<X size={14} />}
            onClick={onClose}
            variant="ghost"
            size="sm"
          />
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FlyoutSurface — floating overlay with drag-to-resize on leading edge
// ---------------------------------------------------------------------------

function FlyoutSurface({
  position,
  title,
  icon,
  onClose,
  onDock,
  children,
}: {
  position: "right" | "bottom";
  title: string;
  icon: ReactNode;
  onClose: () => void;
  onDock?: () => void;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [floatSize, setFloatSize] = useState<number | null>(null);

  const handleEdgeDrag = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      e.preventDefault();
      const startPos = position === "right" ? e.clientX : e.clientY;
      const startSize =
        position === "right"
          ? (panelRef.current?.offsetWidth ?? 500)
          : (panelRef.current?.offsetHeight ?? 320);

      const onMove = (ev: MouseEvent) => {
        const delta = startPos - (position === "right" ? ev.clientX : ev.clientY);
        const min = position === "right" ? 200 : 120;
        const max =
          position === "right"
            ? window.innerWidth * 0.85
            : window.innerHeight * 0.75;
        setFloatSize(Math.max(min, Math.min(max, startSize + delta)));
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [position]
  );

  const base =
    position === "right"
      ? "absolute top-0 right-0 h-full w-[45%]"
      : "absolute bottom-0 left-0 right-0 h-[40%]";
  const borderSide =
    position === "right"
      ? "border-l border-[var(--chat-border)]"
      : "border-t border-[var(--chat-border)]";

  const sizeStyle: React.CSSProperties =
    floatSize !== null
      ? position === "right"
        ? { width: floatSize }
        : { height: floatSize }
      : {};

  return (
    <div
      ref={panelRef}
      className={cn(base, borderSide, "bg-[var(--chat-surface)] z-20 flex flex-col")}
      style={{ boxShadow: "var(--elev-3)", ...sizeStyle }}
    >
      {/* Drag handle on the leading edge */}
      <div
        className={cn(
          "absolute z-30 opacity-0 hover:opacity-100 transition-opacity hover:bg-[var(--chat-accent)]",
          position === "right"
            ? "left-0 top-0 bottom-0 w-1 cursor-ew-resize"
            : "left-0 right-0 top-0 h-1 cursor-ns-resize"
        )}
        onMouseDown={handleEdgeDrag}
      />

      {/* Header */}
      <div
        className="relative flex items-center justify-between px-4 py-2 flex-shrink-0 bg-[var(--chat-surface)]"
        style={{ borderBottom: "1px solid var(--chat-border)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <div
            className="w-6 h-6 rounded-sm flex-shrink-0 flex items-center justify-center text-[var(--chat-accent)]"
            style={{
              background: "var(--chat-accent-soft)",
              border: "1px solid color-mix(in srgb, var(--chat-accent) 25%, var(--chat-border))",
            }}
          >
            {icon}
          </div>
          <span className="text-[13px] font-semibold text-[var(--chat-text)] truncate">{title}</span>
        </div>
        <div className="flex items-center gap-0.5 flex-shrink-0">
          {onDock && (
            <IconButton
              label="Dock panel"
              icon={<Pin size={13} />}
              onClick={onDock}
              variant="ghost"
              size="sm"
              title="Dock to layout"
            />
          )}
          <IconButton
            label={`Close ${title}`}
            icon={<X size={14} />}
            onClick={onClose}
            variant="ghost"
            size="sm"
            onMouseDown={(e) => e.stopPropagation()}
          />
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ViewModeToggle
// ---------------------------------------------------------------------------

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
      <SegmentButton active={viewMode === "code"} onClick={() => onChange("code")} icon={<Code2 size={13} />} label="Chat" />
      <SegmentButton active={viewMode === "preview"} onClick={() => onChange("preview")} icon={<Eye size={13} />} label="Preview" />
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
        active ? "bg-[var(--chat-elevated)] text-[var(--chat-text)]" : "text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
      )}
      style={active ? { boxShadow: "var(--elev-1)" } : undefined}
    >
      <span className={active ? "text-[var(--chat-accent)]" : ""}>{icon}</span>
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// ToolbarButton
// ---------------------------------------------------------------------------

function ToolbarButton({
  onClick,
  active = false,
  title,
  icon,
  label,
  badge,
}: {
  onClick: () => void;
  active?: boolean;
  title: string;
  icon: ReactNode;
  label: string;
  badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn(
        "relative inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] font-medium rounded-md transition-colors border",
        active
          ? "bg-[var(--chat-accent-soft)] text-[var(--chat-accent-strong)] border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))]"
          : "bg-[var(--chat-panel)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] border-[var(--chat-border)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_50%,var(--chat-text))]"
      )}
    >
      <span className={active ? "text-[var(--chat-accent)]" : ""}>{icon}</span>
      {label}
      {badge !== undefined && (
        <span className="ml-0.5 inline-flex items-center justify-center min-w-[16px] h-4 rounded-full bg-[var(--chat-accent)] text-[var(--chat-bg)] text-[9px] font-bold px-1 leading-none">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </button>
  );
}
