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

interface SwarmState {
  active: boolean;
  theaterPhase: SwarmTheaterPhase;
  phaseNum: number;
  phaseName: string;
  workers: SwarmWorker[];
  latestCard: SwarmWorker | null;
  taskSummary: string;

  setActive: (active: boolean) => void;
  setTheaterPhase: (phase: SwarmTheaterPhase) => void;
  setSwarmPhase: (num: number, name: string) => void;
  addWorker: (worker: SwarmWorker) => void;
  updateWorkers: (workers: SwarmWorker[]) => void;
  setLatestCard: (worker: SwarmWorker | null) => void;
  setTaskSummary: (s: string) => void;
  reset: () => void;
}

const INITIAL: Omit<SwarmState, keyof Omit<SwarmState, "active" | "theaterPhase" | "phaseNum" | "phaseName" | "workers" | "latestCard" | "taskSummary">> = {
  active: false,
  theaterPhase: "idle",
  phaseNum: 0,
  phaseName: "",
  workers: [],
  latestCard: null,
  taskSummary: "",
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
    set({ phaseNum, phaseName, theaterPhase });
  },
  addWorker: (worker) =>
    set((s) => ({
      workers: [...s.workers, worker],
      latestCard: worker,
      theaterPhase: "spawning_card",
    })),
  updateWorkers: (incoming) =>
    set((s) => {
      const map = new Map(s.workers.map((w) => [w.worker_id, w]));
      for (const w of incoming) map.set(w.worker_id, { ...map.get(w.worker_id), ...w } as SwarmWorker);
      return { workers: Array.from(map.values()) };
    }),
  setLatestCard: (latestCard) => set({ latestCard }),
  setTaskSummary: (taskSummary) => set({ taskSummary }),
  reset: () => set({ ...INITIAL }),
}));
