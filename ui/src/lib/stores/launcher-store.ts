import { create } from "zustand";

/**
 * Transient handoff from the /launcher route to /chat: a launcher tile stashes
 * the fully-composed message (e.g. "/swarm build a todo app") here, navigates to
 * /chat, and ChatView consumes it once on mount and fires it. Deliberately NOT
 * persisted — a stale launch must never replay on a normal chat visit.
 */
interface PendingLaunch {
  text: string;
}

interface LauncherState {
  pending: PendingLaunch | null;
  setPendingLaunch: (text: string) => void;
  /** Returns the pending launch (if any) and clears it atomically. */
  consumePendingLaunch: () => PendingLaunch | null;
}

export const useLauncherStore = create<LauncherState>((set, get) => ({
  pending: null,
  setPendingLaunch: (text) => set({ pending: { text } }),
  consumePendingLaunch: () => {
    const p = get().pending;
    if (p) set({ pending: null });
    return p;
  },
}));
