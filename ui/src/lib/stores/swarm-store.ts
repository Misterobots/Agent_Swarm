import { create } from "zustand";
import type { SwarmWorker } from "@/types/chat";

export type SwarmTheaterPhase =
  | "idle"
  | "decomposing"
  | "spawning_card"
  | "roster"
  | "working"
  | "synthesizing"
  | "complete";

export interface SwarmState {
  active: boolean;
  theaterPhase: SwarmTheaterPhase;
  phaseNum: number;
  phaseName: string;
  workers: SwarmWorker[];
  latestCard: SwarmWorker | null;
  /** FIFO queue of workers waiting to show their ID-badge animation */
  badgeQueue: SwarmWorker[];
  taskSummary: string;
  selectedWorkerId: string | null;
  /** Soft-collapsed: drawer hidden but state preserved — recall via FAB */
  dismissed: boolean;
  /** True while content is displayed in a detached popup window */
  popoutOpen: boolean;

  setActive: (active: boolean) => void;
  setTheaterPhase: (phase: SwarmTheaterPhase) => void;
  setSwarmPhase: (num: number, name: string) => void;
  addWorker: (worker: SwarmWorker) => void;
  updateWorkers: (workers: SwarmWorker[]) => void;
  setLatestCard: (worker: SwarmWorker | null) => void;
  /** Advance to the next badge in the queue (or transition to roster if empty) */
  dequeueBadge: () => void;
  setTaskSummary: (s: string) => void;
  setSelectedWorker: (id: string | null) => void;
  setDismissed: (dismissed: boolean) => void;
  setPopoutOpen: (open: boolean) => void;
  reset: () => void;
}

const INITIAL: Omit<SwarmState, keyof Omit<SwarmState, "active" | "theaterPhase" | "phaseNum" | "phaseName" | "workers" | "latestCard" | "badgeQueue" | "taskSummary" | "selectedWorkerId" | "dismissed" | "popoutOpen">> = {
  active: false,
  theaterPhase: "idle",
  phaseNum: 0,
  phaseName: "",
  workers: [],
  latestCard: null,
  badgeQueue: [],
  taskSummary: "",
  selectedWorkerId: null,
  dismissed: false,
  popoutOpen: false,
};

export const useSwarmStore = create<SwarmState>()((set) => ({
  ...INITIAL,

  setActive: (active) => set({ active }),
  setTheaterPhase: (theaterPhase) => set({ theaterPhase }),
  setSwarmPhase: (phaseNum, phaseName) => {
    let theaterPhase: SwarmTheaterPhase = "working";
    if (phaseNum === 1) theaterPhase = "decomposing";
    else if (phaseNum === 2) theaterPhase = "roster";
    else if (phaseNum === 3) theaterPhase = "synthesizing";
    else if (phaseNum >= 4) theaterPhase = "working";
    // Don't overwrite spawning_card — let the card animation finish
    set((s) => ({
      phaseNum,
      phaseName,
      ...(s.theaterPhase !== "spawning_card" ? { theaterPhase } : {}),
    }));
  },
  addWorker: (worker) =>
    set((s) => {
      const newQueue = [...s.badgeQueue, worker];
      const alreadyAnimating = s.theaterPhase === "spawning_card";
      return {
        workers: [...s.workers, worker],
        badgeQueue: newQueue,
        // Only start showing the first card if not already animating;
        // subsequent cards are driven by dequeueBadge as each animation finishes
        ...(alreadyAnimating ? {} : {
          latestCard: worker,
          theaterPhase: "spawning_card" as SwarmTheaterPhase,
        }),
      };
    }),
  dequeueBadge: () =>
    set((s) => {
      const remaining = s.badgeQueue.slice(1);
      return {
        badgeQueue: remaining,
        latestCard: remaining[0] ?? null,
        theaterPhase: (remaining.length > 0 ? "spawning_card" : "roster") as SwarmTheaterPhase,
      };
    }),
  updateWorkers: (incoming) =>
    set((s) => {
      const map = new Map(s.workers.map((w) => [w.worker_id, w]));
      for (const w of incoming) map.set(w.worker_id, { ...map.get(w.worker_id), ...w } as SwarmWorker);
      return { workers: Array.from(map.values()) };
    }),
  setLatestCard: (latestCard) => set({ latestCard }),
  setTaskSummary: (taskSummary) => set({ taskSummary }),
  setSelectedWorker: (selectedWorkerId) => set({ selectedWorkerId }),
  setDismissed: (dismissed) => set({ dismissed }),
  setPopoutOpen: (popoutOpen) => set({ popoutOpen }),
  reset: () => set({ ...INITIAL }),
}));
