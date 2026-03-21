import { create } from "zustand";
import { persist } from "zustand/middleware";

interface MonitorState {
  activeDashboard: string;
  setActiveDashboard: (id: string) => void;
}

export const useMonitorStore = create<MonitorState>()(
  persist(
    (set) => ({
      activeDashboard: "mission-control-uid",
      setActiveDashboard: (id) => set({ activeDashboard: id }),
    }),
    { name: "hive-monitor" }
  )
);
