import { create } from "zustand";
import { persist } from "zustand/middleware";

interface TerminalTabInfo {
  id: string;
  title: string;
}

interface DevState {
  editorContent: string;
  editorLanguage: string;
  activeFile: string;
  selectedText: string;

  // Phase 2: AI agentic coding settings
  /** When true, send dev_mode=true in chat requests to enable agentic tools */
  agentEnabled: boolean;
  /** When true, auto-sync Monaco editor content when AI writes the active file */
  editorSyncEnabled: boolean;
  /** Tool names the user has auto-approved for the current session */
  sessionAutoApprove: string[];
  
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
  
  // Flyout panels (Gemini-style)
  showEditorPanel: boolean;
  showTerminalPanel: boolean;
  
  // View mode: 'preview' (live output) or 'code' (editor + file tree)
  viewMode: "preview" | "code";

  setEditorContent: (content: string) => void;
  setEditorLanguage: (language: string) => void;
  setActiveFile: (file: string) => void;
  setSelectedText: (text: string) => void;
  setAgentEnabled: (enabled: boolean) => void;
  setEditorSyncEnabled: (enabled: boolean) => void;
  addSessionAutoApprove: (toolName: string) => void;
  clearSessionAutoApprove: () => void;
  
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
  
  // Flyout panel actions
  setShowEditorPanel: (show: boolean) => void;
  setShowTerminalPanel: (show: boolean) => void;
  toggleEditorPanel: () => void;
  toggleTerminalPanel: () => void;
  setViewMode: (mode: "preview" | "code") => void;
}

export const useDevStore = create<DevState>()(
  persist(
    (set) => ({
      editorContent: "# Start coding here\n",
      editorLanguage: "python",
      activeFile: "",
      selectedText: "",
      agentEnabled: true,
      editorSyncEnabled: true,
      sessionAutoApprove: [],
      terminalTabs: [],
      activeTerminalId: "",
      selectedNode: "workspace",
      gitBranch: {},
      previewUrl: "",
      showFileTree: true,
      showOutputPreview: true,
      showChatPreview: false,
      previewUnavailable: false,
      showEditorPanel: false,
      showTerminalPanel: false,
      viewMode: "code",
      
      setEditorContent: (content) => set({ editorContent: content }),
      setEditorLanguage: (language) => set({ editorLanguage: language }),
      setActiveFile: (file) => set({ activeFile: file }),
      setSelectedText: (text) => set({ selectedText: text }),
      setAgentEnabled: (enabled) => set({ agentEnabled: enabled }),
      setEditorSyncEnabled: (enabled) => set({ editorSyncEnabled: enabled }),
      addSessionAutoApprove: (toolName) =>
        set((s) => ({ sessionAutoApprove: [...new Set([...s.sessionAutoApprove, toolName])] })),
      clearSessionAutoApprove: () => set({ sessionAutoApprove: [] }),
      
      addTerminalTab: (id, title) =>
        set((s) => ({ terminalTabs: [...s.terminalTabs, { id, title }] })),
      removeTerminalTab: (id) =>
        set((s) => ({
          terminalTabs: s.terminalTabs.filter((t) => t.id !== id),
          activeTerminalId: s.activeTerminalId === id ? (s.terminalTabs[0]?.id || "") : s.activeTerminalId,
        })),
      setActiveTerminal: (id) => set({ activeTerminalId: id }),
      
      setSelectedNode: (node) => set({ selectedNode: node }),
      setGitBranch: (node, branch) =>
        set((s) => ({ gitBranch: { ...s.gitBranch, [node]: branch } })),
      
      setPreviewUrl: (url) => set({ previewUrl: url, ...(url ? { showChatPreview: true, previewUnavailable: false } : {}) }),
      setShowFileTree: (show) => set({ showFileTree: show }),
      setShowOutputPreview: (show) => set({ showOutputPreview: show }),
      setShowChatPreview: (show) => set({ showChatPreview: show }),
      setPreviewUnavailable: (unavailable) => set({ previewUnavailable: unavailable }),
      
      setShowEditorPanel: (show) => set({ showEditorPanel: show }),
      setShowTerminalPanel: (show) => set({ showTerminalPanel: show }),
      toggleEditorPanel: () => set((s) => ({ showEditorPanel: !s.showEditorPanel })),
      toggleTerminalPanel: () => set((s) => ({ showTerminalPanel: !s.showTerminalPanel })),
      setViewMode: (mode) => set({ viewMode: mode }),
    }),
    {
      name: "memex-dev-store",
      // Persist settings and state
      partialize: (state) => ({
        agentEnabled: state.agentEnabled,
        editorSyncEnabled: state.editorSyncEnabled,
        selectedNode: state.selectedNode,
        // previewUrl is intentionally NOT persisted — it defaults to empty so
        // the pane shows a friendly empty state rather than loading a stale URL.
        showFileTree: state.showFileTree,
        showOutputPreview: state.showOutputPreview,
        showEditorPanel: state.showEditorPanel,
        viewMode: state.viewMode,
        // Note: showTerminalPanel is NOT persisted - always starts closed
      }),
    }
  )
);

