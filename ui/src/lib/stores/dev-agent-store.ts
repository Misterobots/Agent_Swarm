/**
 * Dev Agent slice — owns: agentEnabled, editorSyncEnabled, sessionAutoApprove.
 * Primary writer: task Q1.
 *
 * New code should import from this store directly rather than via the dev-store facade.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface DevAgentState {
  /** When true, send dev_mode=true in chat requests to enable agentic tools. */
  agentEnabled: boolean;
  /** When true, auto-sync Monaco editor content when AI writes the active file. */
  editorSyncEnabled: boolean;
  /** Tool names the user has auto-approved for the current session. */
  sessionAutoApprove: string[];

  setAgentEnabled: (enabled: boolean) => void;
  setEditorSyncEnabled: (enabled: boolean) => void;
  addSessionAutoApprove: (toolName: string) => void;
  clearSessionAutoApprove: () => void;
}

export const useDevAgentStore = create<DevAgentState>()(
  persist(
    (set) => ({
      agentEnabled: true,
      editorSyncEnabled: true,
      sessionAutoApprove: [],

      setAgentEnabled: (enabled) => set({ agentEnabled: enabled }),
      setEditorSyncEnabled: (enabled) => set({ editorSyncEnabled: enabled }),
      addSessionAutoApprove: (toolName) =>
        set((s) => ({
          sessionAutoApprove: [...new Set([...s.sessionAutoApprove, toolName])],
        })),
      clearSessionAutoApprove: () => set({ sessionAutoApprove: [] }),
    }),
    {
      name: "memex-dev-agent-store",
      partialize: (state) => ({
        agentEnabled: state.agentEnabled,
        editorSyncEnabled: state.editorSyncEnabled,
        sessionAutoApprove: state.sessionAutoApprove,
      }),
    }
  )
);
