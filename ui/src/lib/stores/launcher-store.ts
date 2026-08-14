import { create } from "zustand";

/**
 * One-shot handoff for tools that launch work in the primary chat workspace.
 * It intentionally is not persisted: a completed launch must never replay on
 * a later app start or in another browser tab.
 */
interface LauncherState {
  pendingLaunch: string | null;
  setPendingLaunch: (prompt: string) => void;
  consumePendingLaunch: () => string | null;
}

export const useLauncherStore = create<LauncherState>((set, get) => ({
  pendingLaunch: null,
  setPendingLaunch: (prompt) => set({ pendingLaunch: prompt }),
  consumePendingLaunch: () => {
    const prompt = get().pendingLaunch;
    set({ pendingLaunch: null });
    return prompt;
  },
}));
