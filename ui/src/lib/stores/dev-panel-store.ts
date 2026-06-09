/**
 * Dev Panel slice — owns: show* flags, viewMode, terminalTabs, selectedNode, previewUrl, etc.
 * Primary writer: task P0.
 *
 * New code should import from this store directly rather than via the dev-store facade.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface TerminalTabInfo {
  id: string;
  title: string;
}

export interface DevPanelState {
  // Flyout panels (Gemini-style)
  showEditorPanel: boolean;
  showTerminalPanel: boolean;
  /** Generic panel show state keyed by panel id — used by panel registry */
  showPanel: Record<string, boolean>;
  /** Whether each panel is docked (inline layout) vs floating (overlay). Default: true (docked). */
  panelDocked: Record<string, boolean>;

  // View mode: 'preview' (live output) or 'code' (editor + file tree)
  viewMode: "preview" | "code";

  // Phase 2: Terminal tabs
  terminalTabs: TerminalTabInfo[];
  activeTerminalId: string;

  // Phase 2: Admin features
  selectedNode: "lovelace" | "turing" | "hopper" | "workspace";
  gitBranch: { [node: string]: string };

  // Phase 2: Output preview
  previewUrl: string;
  showFileTree: boolean;
  showOutputPreview: boolean;

  // Chat preview pane (slides in on /chat when a build completes)
  showChatPreview: boolean;
  previewUnavailable: boolean;

  // Flyout panel actions
  setShowEditorPanel: (show: boolean) => void;
  setShowTerminalPanel: (show: boolean) => void;
  toggleEditorPanel: () => void;
  toggleTerminalPanel: () => void;
  /** Toggle any panel by id — works for both built-in and registry panels */
  togglePanel: (id: string) => void;
  /** Set whether a panel is docked (inline) or floating (overlay) */
  setPanelDocked: (id: string, docked: boolean) => void;
  setViewMode: (mode: "preview" | "code") => void;

  // Terminal tab actions
  addTerminalTab: (id: string, title: string) => void;
  removeTerminalTab: (id: string) => void;
  setActiveTerminal: (id: string) => void;

  // Admin actions
  setSelectedNode: (node: "lovelace" | "turing" | "hopper" | "workspace") => void;
  setGitBranch: (node: string, branch: string) => void;

  // Preview actions
  setPreviewUrl: (url: string) => void;
  setShowFileTree: (show: boolean) => void;
  setShowOutputPreview: (show: boolean) => void;
  setShowChatPreview: (show: boolean) => void;
  setPreviewUnavailable: (unavailable: boolean) => void;
}

export const useDevPanelStore = create<DevPanelState>()(
  persist(
    (set) => ({
      showEditorPanel: false,
      showTerminalPanel: false,
      showPanel: {},
      panelDocked: {},   // empty = "use default" → all panels default to docked (true)
      viewMode: "code",
      terminalTabs: [],
      activeTerminalId: "",
      selectedNode: "workspace",
      gitBranch: {},
      previewUrl: "",
      showFileTree: true,
      showOutputPreview: true,
      showChatPreview: false,
      previewUnavailable: false,

      setShowEditorPanel: (show) =>
        set((s) => ({ showEditorPanel: show, showPanel: { ...s.showPanel, editor: show } })),
      setShowTerminalPanel: (show) =>
        set((s) => ({ showTerminalPanel: show, showPanel: { ...s.showPanel, terminal: show } })),
      toggleEditorPanel: () =>
        set((s) => {
          const next = !s.showEditorPanel;
          return { showEditorPanel: next, showPanel: { ...s.showPanel, editor: next } };
        }),
      toggleTerminalPanel: () =>
        set((s) => {
          const next = !s.showTerminalPanel;
          return { showTerminalPanel: next, showPanel: { ...s.showPanel, terminal: next } };
        }),
      togglePanel: (id) =>
        set((s) => {
          const next = !s.showPanel[id];
          const update: Partial<DevPanelState> = { showPanel: { ...s.showPanel, [id]: next } };
          if (id === "editor") update.showEditorPanel = next;
          if (id === "terminal") update.showTerminalPanel = next;
          return update;
        }),
      setPanelDocked: (id, docked) =>
        set((s) => ({ panelDocked: { ...s.panelDocked, [id]: docked } })),
      setViewMode: (mode) => set({ viewMode: mode }),

      addTerminalTab: (id, title) =>
        set((s) => ({ terminalTabs: [...s.terminalTabs, { id, title }] })),
      removeTerminalTab: (id) =>
        set((s) => ({
          terminalTabs: s.terminalTabs.filter((t) => t.id !== id),
          activeTerminalId:
            s.activeTerminalId === id ? (s.terminalTabs[0]?.id || "") : s.activeTerminalId,
        })),
      setActiveTerminal: (id) => set({ activeTerminalId: id }),

      setSelectedNode: (node) => set({ selectedNode: node }),
      setGitBranch: (node, branch) =>
        set((s) => ({ gitBranch: { ...s.gitBranch, [node]: branch } })),

      setPreviewUrl: (url) =>
        set({ previewUrl: url, ...(url ? { showChatPreview: true, previewUnavailable: false } : {}) }),
      setShowFileTree: (show) => set({ showFileTree: show }),
      setShowOutputPreview: (show) => set({ showOutputPreview: show }),
      setShowChatPreview: (show) => set({ showChatPreview: show }),
      setPreviewUnavailable: (unavailable) => set({ previewUnavailable: unavailable }),
    }),
    {
      name: "memex-dev-panel-store",
      partialize: (state) => ({
        selectedNode: state.selectedNode,
        showFileTree: state.showFileTree,
        showOutputPreview: state.showOutputPreview,
        showEditorPanel: state.showEditorPanel,
        viewMode: state.viewMode,
        // showTerminalPanel is intentionally NOT persisted — always starts closed
        // showPanel keys are persisted so registry panels survive reloads
        showPanel: state.showPanel,
        panelDocked: state.panelDocked,
      }),
    }
  )
);
