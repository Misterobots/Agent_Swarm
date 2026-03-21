import { create } from "zustand";

interface OpsState {
  refreshInterval: number;
  setRefreshInterval: (interval: number) => void;
}

export const useOpsStore = create<OpsState>((set) => ({
  refreshInterval: 30000,
  setRefreshInterval: (interval) => set({ refreshInterval: interval }),
}));
