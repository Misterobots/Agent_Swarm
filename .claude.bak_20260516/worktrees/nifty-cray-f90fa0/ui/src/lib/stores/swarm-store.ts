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
  /** Workers whose badge animation has completed — used to progressively fill roster */
  revealedWorkerIds: string[];
  /** Maps phase number (as string) → phase name for display in timeline dividers */
  phaseNameMap: Record<string, string>;
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

const INITIAL: Omit<SwarmState, keyof Omit<SwarmState, "active" | "theaterPhase" | "phaseNum" | "phaseName" | "workers" | "latestCard" | "badgeQueue" | "revealedWorkerIds" | "phaseNameMap" | "taskSummary" | "selectedWorkerId" | "dismissed" | "popoutOpen">> = {
  active: false,
  theaterPhase: "idle",
  phaseNum: 0,
  phaseName: "",
  workers: [],
  latestCard: null,
  badgeQueue: [],
  revealedWorkerIds: [],
  phaseNameMap: {},
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
      // Record phase name for timeline dividers
      phaseNameMap: phaseName ? { ...s.phaseNameMap, [String(phaseNum)]: phaseName } : s.phaseNameMap,
      ...(s.theaterPhase !== "spawning_card" ? { theaterPhase } : {}),
    }));
  },
  addWorker: (worker) =>
    set((s) => {
      // Dedup: if updateWorkers already added this worker to both workers list
      // AND the badge queue, skip entirely to avoid double-animation.
      const alreadyInWorkers = s.workers.some((w) => w.worker_id === worker.worker_id);
      const alreadyQueued =
        s.latestCard?.worker_id === worker.worker_id ||
        s.badgeQueue.some((w) => w.worker_id === worker.worker_id);
      if (alreadyInWorkers && alreadyQueued) return s;

      const newWorkers = alreadyInWorkers ? s.workers : [...s.workers, worker];
      const newQueue = alreadyQueued ? s.badgeQueue : [...s.badgeQueue, worker];
      const alreadyAnimating = s.theaterPhase === "spawning_card";
      return {
        workers: newWorkers,
        badgeQueue: newQueue,
        ...(alreadyAnimating ? {} : {
          latestCard: newQueue[0] ?? worker,
          theaterPhase: "spawning_card" as SwarmTheaterPhase,
          revealedWorkerIds: [], // Reset for fresh badge cycle
        }),
      };
    }),
  dequeueBadge: () =>
    set((s) => {
      const justDone = s.latestCard?.worker_id ?? null;
      const remaining = s.badgeQueue.slice(1);
      return {
        badgeQueue: remaining,
        latestCard: remaining[0] ?? null,
        theaterPhase: (remaining.length > 0 ? "spawning_card" : "roster") as SwarmTheaterPhase,
        revealedWorkerIds: justDone
          ? [...s.revealedWorkerIds, justDone]
          : s.revealedWorkerIds,
      };
    }),
  updateWorkers: (incoming) =>
    set((s) => {
      // Any worker not already in the workers list AND not already queued/showing
      // must go through the badge animation queue — same as addWorker.
      const existingIds = new Set(s.workers.map((w) => w.worker_id));
      const queuedIds = new Set([
        ...(s.latestCard ? [s.latestCard.worker_id] : []),
        ...s.badgeQueue.map((w) => w.worker_id),
      ]);
      const brandNew = incoming.filter(
        (w) => !existingIds.has(w.worker_id) && !queuedIds.has(w.worker_id),
      );

      const map = new Map(s.workers.map((w) => [w.worker_id, w]));
      for (const w of incoming) map.set(w.worker_id, { ...map.get(w.worker_id), ...w } as SwarmWorker);

      const newQueue = [...s.badgeQueue, ...brandNew];
      const alreadyAnimating = s.theaterPhase === "spawning_card";

      return {
        workers: Array.from(map.values()),
        badgeQueue: newQueue,
        ...(brandNew.length > 0 && !alreadyAnimating && newQueue.length > 0
          ? {
              latestCard: newQueue[0],
              theaterPhase: "spawning_card" as SwarmTheaterPhase,
              revealedWorkerIds: [], // Reset for fresh badge cycle
            }
          : {}),
      };
    }),
  setLatestCard: (latestCard) => set({ latestCard }),
  setTaskSummary: (taskSummary) => set({ taskSummary }),
  setSelectedWorker: (selectedWorkerId) => set({ selectedWorkerId }),
  setDismissed: (dismissed) => set({ dismissed }),
  setPopoutOpen: (popoutOpen) => set({ popoutOpen }),
  reset: () => set({ ...INITIAL }),
}));
