import { create } from "zustand";
import { persist } from "zustand/middleware";

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

  setEditorContent: (content: string) => void;
  setEditorLanguage: (language: string) => void;
  setActiveFile: (file: string) => void;
  setSelectedText: (text: string) => void;
  setAgentEnabled: (enabled: boolean) => void;
  setEditorSyncEnabled: (enabled: boolean) => void;
  addSessionAutoApprove: (toolName: string) => void;
  clearSessionAutoApprove: () => void;
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
      setEditorContent: (content) => set({ editorContent: content }),
      setEditorLanguage: (language) => set({ editorLanguage: language }),
      setActiveFile: (file) => set({ activeFile: file }),
      setSelectedText: (text) => set({ selectedText: text }),
      setAgentEnabled: (enabled) => set({ agentEnabled: enabled }),
      setEditorSyncEnabled: (enabled) => set({ editorSyncEnabled: enabled }),
      addSessionAutoApprove: (toolName) =>
        set((s) => ({ sessionAutoApprove: [...new Set([...s.sessionAutoApprove, toolName])] })),
      clearSessionAutoApprove: () => set({ sessionAutoApprove: [] }),
    }),
    {
      name: "hive-dev-store",
      // Only persist settings, not transient editor state
      partialize: (state) => ({
        agentEnabled: state.agentEnabled,
        editorSyncEnabled: state.editorSyncEnabled,
      }),
    }
  )
);
