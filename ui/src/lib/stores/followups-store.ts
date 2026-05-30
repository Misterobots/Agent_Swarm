// ui/src/lib/stores/followups-store.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { FlaggedFollowup } from "@/types/chat";

interface FollowupsState {
  /** All flagged follow-up items, newest first. */
  followups: FlaggedFollowup[];

  /** Prepend a new follow-up to the queue. */
  addFollowup: (followup: FlaggedFollowup) => void;

  /** Remove a follow-up by id. */
  removeFollowup: (id: string) => void;

  /** Wipe the entire queue. */
  clearAll: () => void;
}

export const useFollowupsStore = create<FollowupsState>()(
  persist(
    (set) => ({
      followups: [],

      addFollowup: (followup) =>
        set((state) => ({ followups: [followup, ...state.followups] })),

      removeFollowup: (id) =>
        set((state) => ({
          followups: state.followups.filter((f) => f.id !== id),
        })),

      clearAll: () => set({ followups: [] }),
    }),
    { name: "memex-followups" }
  )
);
